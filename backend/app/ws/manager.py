"""WebSocket connection manager with intelligent backpressure.

Per-scenario fan-out of tick diffs to subscribed clients. Backpressure (ROLE_5: "drop frames
intelligently, not queue forever"): each connection has a small bounded queue. If a client can't
keep up, we drop the *oldest* frame rather than blocking the sim or growing memory without bound.
Metrics still arrive on later frames, so a dropped frame just means that client skips an update.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket

from app.models.schemas import WSMessage

logger = logging.getLogger(__name__)

_QUEUE_MAXSIZE = 8  # frames buffered per client before we start dropping oldest


class _Connection:
    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self.queue: asyncio.Queue[WSMessage] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self.dropped = 0

    def offer(self, message: WSMessage) -> None:
        """Non-blocking enqueue; drop the oldest frame if the client is behind."""
        if self.queue.full():
            try:
                self.queue.get_nowait()
                self.dropped += 1
            except asyncio.QueueEmpty:  # pragma: no cover - race guard
                pass
        self.queue.put_nowait(message)


class ConnectionManager:
    def __init__(self) -> None:
        # scenario_id -> set of connections
        self._rooms: dict[str, set[_Connection]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, scenario_id: str, ws: WebSocket) -> _Connection:
        await ws.accept()
        conn = _Connection(ws)
        async with self._lock:
            self._rooms.setdefault(scenario_id, set()).add(conn)
        logger.info("WS connected to %s (%d clients)", scenario_id, self.client_count(scenario_id))
        return conn

    async def disconnect(self, scenario_id: str, conn: _Connection) -> None:
        async with self._lock:
            room = self._rooms.get(scenario_id)
            if room:
                room.discard(conn)
                if not room:
                    self._rooms.pop(scenario_id, None)

    def client_count(self, scenario_id: str) -> int:
        return len(self._rooms.get(scenario_id, ()))

    async def broadcast(self, scenario_id: str, message: WSMessage) -> None:
        """Offer a frame to every client in the room (non-blocking)."""
        for conn in list(self._rooms.get(scenario_id, ())):
            conn.offer(message)

    async def pump(self, conn: _Connection) -> None:
        """Drain one connection's queue to its socket. Runs per-connection."""
        while True:
            message = await conn.queue.get()
            await conn.ws.send_text(message.model_dump_json())
