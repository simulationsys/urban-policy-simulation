"""Scenario lifecycle + the per-scenario tick loop.

This is the heart of the backend. It owns:
- One ``SimEngine`` instance per scenario (the seam to SUB-01).
- The async tick loop: advance the engine, record the snapshot, broadcast a diff over WebSocket.
- Lifecycle transitions: create / start / pause / resume / reset / branch / delete.
- Event injection: user events are queued on the engine and applied at the next tick boundary.

All sim logic stays behind the engine adapter — this module orchestrates, it does not model.
"""

from __future__ import annotations

import asyncio
import logging

from app.config import Settings
from app.models.schemas import (
    Event,
    EventAck,
    ScenarioConfig,
    ScenarioStatus,
    ScenarioSummary,
    Snapshot,
    TickDiff,
    WSMessage,
    WSMessageType,
)
from app.sim.adapter import SimEngine, build_engine
from app.store.metadata import MetadataStore
from app.store.state import StateStore
from app.ws.manager import ConnectionManager

logger = logging.getLogger(__name__)


class ScenarioManager:
    def __init__(
        self,
        settings: Settings,
        metadata: MetadataStore,
        state: StateStore,
        ws: ConnectionManager,
    ) -> None:
        self._settings = settings
        self._metadata = metadata
        self._state = state
        self._ws = ws
        self._engines: dict[str, SimEngine] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}

    # --- lifecycle -----------------------------------------------------------------------
    def create(self, config: ScenarioConfig) -> ScenarioSummary:
        summary = self._metadata.create(config)
        self._engines[summary.id] = build_engine(self._settings.sim_engine, config)
        self._state.ensure(summary.id)
        logger.info("Created %s (engine=%s)", summary.id, self._settings.sim_engine)
        return summary

    def list(self) -> list[ScenarioSummary]:
        return self._metadata.list()

    def get(self, scenario_id: str) -> ScenarioSummary | None:
        return self._metadata.get(scenario_id)

    def start(self, scenario_id: str) -> ScenarioSummary:
        summary = self._require(scenario_id)
        if scenario_id in self._tasks and not self._tasks[scenario_id].done():
            return summary  # already running
        self._metadata.update_status(scenario_id, ScenarioStatus.running)
        self._tasks[scenario_id] = asyncio.create_task(self._run_loop(scenario_id))
        return self._require(scenario_id)

    def pause(self, scenario_id: str) -> ScenarioSummary:
        self._require(scenario_id)
        self._cancel_task(scenario_id)
        self._metadata.update_status(scenario_id, ScenarioStatus.paused)
        return self._require(scenario_id)

    def resume(self, scenario_id: str) -> ScenarioSummary:
        return self.start(scenario_id)

    def reset(self, scenario_id: str) -> ScenarioSummary:
        summary = self._require(scenario_id)
        self._cancel_task(scenario_id)
        # Rebuild the engine from the original config + seed → identical fresh run.
        self._engines[scenario_id] = build_engine(self._settings.sim_engine, summary.config)
        self._state.drop(scenario_id)
        self._state.ensure(scenario_id)
        self._metadata.update_tick(scenario_id, 0)
        self._metadata.update_status(scenario_id, ScenarioStatus.created)
        return self._require(scenario_id)

    def branch(self, scenario_id: str, new_name: str) -> ScenarioSummary:
        """Fork at the current tick into a new independent scenario.

        v1 keeps it simple: the branch starts from the parent's config (same seed) and a fresh
        engine. A future version can deep-copy live engine state for a true mid-run fork.
        """
        parent = self._require(scenario_id)
        child_config = parent.config.model_copy(update={"name": new_name})
        return self.create(child_config)

    def delete(self, scenario_id: str) -> None:
        self._cancel_task(scenario_id)
        self._engines.pop(scenario_id, None)
        self._state.drop(scenario_id)
        self._metadata.delete(scenario_id)

    # --- events --------------------------------------------------------------------------
    def inject_event(self, scenario_id: str, event: Event) -> EventAck:
        engine = self._engine(scenario_id)
        queued_for = engine.queue_event(event)
        logger.info("Queued %s on %s for tick %d", event.type, scenario_id, queued_for)
        return EventAck(
            accepted=True, scenario_id=scenario_id, queued_for_tick=queued_for, event=event
        )

    # --- snapshots / metrics -------------------------------------------------------------
    def current_snapshot(self, scenario_id: str) -> Snapshot:
        st = self._state.get(scenario_id)
        if st and st.latest:
            return st.latest
        # Not started yet — return the engine's tick-0 snapshot.
        snap = self._engine(scenario_id).snapshot()
        snap.scenario_id = scenario_id
        return snap

    # --- the tick loop -------------------------------------------------------------------
    async def _run_loop(self, scenario_id: str) -> None:
        engine = self._engine(scenario_id)
        interval = self._settings.tick_interval_seconds
        st = self._state.ensure(scenario_id)
        prev_cells: dict[tuple[float, float], float] = {}
        try:
            while True:
                snap = engine.step()
                snap.scenario_id = scenario_id
                st.record(snap)
                self._metadata.update_tick(scenario_id, snap.tick)

                # Diff: stream only changed cells (ROLE_5: smallest thing that conveys change).
                changed = []
                for cell in snap.grid:
                    key = (cell.lat, cell.lon)
                    if prev_cells.get(key) != cell.congestion:
                        changed.append(cell)
                        prev_cells[key] = cell.congestion

                diff = TickDiff(
                    scenario_id=scenario_id,
                    tick=snap.tick,
                    metrics=snap.metrics,
                    changed_cells=changed,
                )
                await self._ws.broadcast(
                    scenario_id,
                    WSMessage(
                        type=WSMessageType.tick,
                        scenario_id=scenario_id,
                        tick=snap.tick,
                        diff=diff,
                    ),
                )
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover - defensive
            logger.exception("Tick loop crashed for %s", scenario_id)
            self._metadata.update_status(scenario_id, ScenarioStatus.error)
            await self._ws.broadcast(
                scenario_id,
                WSMessage(
                    type=WSMessageType.error,
                    scenario_id=scenario_id,
                    status=ScenarioStatus.error,
                    message="Simulation tick loop failed.",
                ),
            )

    # --- shutdown ------------------------------------------------------------------------
    async def shutdown(self) -> None:
        for sid in list(self._tasks):
            self._cancel_task(sid)
        # Give cancellations a moment to propagate.
        await asyncio.gather(*(t for t in self._tasks.values()), return_exceptions=True)

    # --- helpers -------------------------------------------------------------------------
    def _cancel_task(self, scenario_id: str) -> None:
        task = self._tasks.pop(scenario_id, None)
        if task and not task.done():
            task.cancel()

    def _engine(self, scenario_id: str) -> SimEngine:
        engine = self._engines.get(scenario_id)
        if engine is None:
            # Lazily rebuild from metadata (e.g. after a process restart).
            summary = self._require(scenario_id)
            engine = build_engine(self._settings.sim_engine, summary.config)
            self._engines[scenario_id] = engine
            self._state.ensure(scenario_id)
        return engine

    def _require(self, scenario_id: str) -> ScenarioSummary:
        summary = self._metadata.get(scenario_id)
        if summary is None:
            raise KeyError(scenario_id)
        return summary
