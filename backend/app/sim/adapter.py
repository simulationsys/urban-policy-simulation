"""The seam to the Simulation Core (SUB-01).

The backend depends on this Protocol, never on a concrete engine. When SUB-01 is ready, it
implements ``SimEngine`` (e.g. a Mesa-backed engine) and we select it via ``Settings.sim_engine``.
Until then, ``fake_engine.FakeSimEngine`` satisfies the Protocol so the full vertical slice
(data → sim → API → UI) runs today.

Keeping sim logic *behind* this boundary is deliberate: API handlers must not contain business
logic (ROLE_5 anti-pattern).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.models.schemas import Event, ScenarioConfig, Snapshot


@runtime_checkable
class SimEngine(Protocol):
    """Minimal contract every simulation engine must satisfy.

    An engine instance owns exactly one scenario run's world state. The backend creates one engine
    per scenario, advances it one tick at a time, and reads snapshots out.
    """

    config: ScenarioConfig

    @property
    def current_tick(self) -> int:
        """Ticks completed so far (0 before the first ``step``)."""
        ...

    def queue_event(self, event: Event) -> int:
        """Queue an event for injection at the next tick boundary.

        Returns the tick number the event is queued for (PROJECT_SPEC §8.3).
        """
        ...

    def step(self) -> Snapshot:
        """Advance exactly one tick and return the resulting full snapshot.

        Per-tick procedure (PROJECT_SPEC §8.2): advance clock, update environment, apply pending
        events, activate agents, update network, compute metrics, emit snapshot.
        """
        ...

    def snapshot(self) -> Snapshot:
        """Return the current full snapshot without advancing time."""
        ...


def build_engine(engine_kind: str, config: ScenarioConfig) -> SimEngine:
    """Factory. Add real engines here as SUB-01 delivers them."""
    if engine_kind == "fake":
        from app.sim.fake_engine import FakeSimEngine

        return FakeSimEngine(config)
    # if engine_kind == "mesa":
    #     from app.sim.mesa_engine import MesaSimEngine
    #     return MesaSimEngine(config)
    raise ValueError(f"Unknown sim engine: {engine_kind!r} (expected 'fake' or 'mesa')")
