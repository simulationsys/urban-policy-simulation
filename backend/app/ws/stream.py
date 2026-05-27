"""Live tick stream endpoint: /ws/scenarios/{scenario_id}.

The client connects, receives an initial ``status`` frame, then a ``tick`` frame per simulated tick
(diffs only). Backpressure is handled by the ConnectionManager (oldest frame dropped if a client
falls behind). The client may also send a JSON event over the same socket to inject it.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.models.schemas import Event, WSMessage, WSMessageType
from app.services.scenario_manager import ScenarioManager
from app.ws.manager import ConnectionManager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/scenarios/{scenario_id}")
async def scenario_stream(websocket: WebSocket, scenario_id: str) -> None:
    manager: ScenarioManager = websocket.app.state.scenario_manager
    ws_manager: ConnectionManager = websocket.app.state.ws_manager

    if manager.get(scenario_id) is None:
        await websocket.close(code=4404, reason="scenario not found")
        return

    conn = await ws_manager.connect(scenario_id, websocket)

    # Initial status frame so the client knows where the run is.
    summary = manager.get(scenario_id)
    await websocket.send_text(
        WSMessage(
            type=WSMessageType.status,
            scenario_id=scenario_id,
            tick=summary.current_tick if summary else 0,
            status=summary.status if summary else None,
        ).model_dump_json()
    )

    # One task drains queued frames to the socket; the main coroutine reads inbound events.
    pump_task = asyncio.create_task(ws_manager.pump(conn))
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                event = Event.model_validate_json(raw)
            except ValidationError as exc:
                await websocket.send_text(
                    WSMessage(
                        type=WSMessageType.error,
                        scenario_id=scenario_id,
                        message=f"Invalid event: {exc.error_count()} error(s)",
                    ).model_dump_json()
                )
                continue
            manager.inject_event(scenario_id, event)
    except WebSocketDisconnect:
        pass
    finally:
        pump_task.cancel()
        await ws_manager.disconnect(scenario_id, conn)
