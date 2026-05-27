"""In-process state store (PROJECT_SPEC §5.3: in-process dict for v1; Redis only if needed).

Holds the latest snapshot and a bounded ring buffer of recent ticks per scenario, so REST clients
can fetch history and the metrics endpoint can serve a window without touching disk. Long-term
history belongs in Parquet (written by the sim/data layers), not here.
"""

from __future__ import annotations

from collections import deque

from app.models.schemas import AggregateMetrics, Snapshot


class ScenarioState:
    def __init__(self, buffer_size: int) -> None:
        self.latest: Snapshot | None = None
        self._snapshots: deque[Snapshot] = deque(maxlen=buffer_size)
        self._metrics: deque[AggregateMetrics] = deque(maxlen=buffer_size)

    def record(self, snapshot: Snapshot) -> None:
        self.latest = snapshot
        self._snapshots.append(snapshot)
        self._metrics.append(snapshot.metrics)

    def snapshot_at(self, tick: int) -> Snapshot | None:
        # Linear scan over a bounded buffer — fine at this scale.
        for snap in reversed(self._snapshots):
            if snap.tick == tick:
                return snap
        return None

    def metric_window(self, from_tick: int, to_tick: int) -> list[AggregateMetrics]:
        return [m for m in self._metrics if from_tick <= m.tick <= to_tick]


class StateStore:
    """All live scenario state, keyed by scenario id."""

    def __init__(self, buffer_size: int) -> None:
        self._buffer_size = buffer_size
        self._states: dict[str, ScenarioState] = {}

    def ensure(self, scenario_id: str) -> ScenarioState:
        return self._states.setdefault(scenario_id, ScenarioState(self._buffer_size))

    def get(self, scenario_id: str) -> ScenarioState | None:
        return self._states.get(scenario_id)

    def drop(self, scenario_id: str) -> None:
        self._states.pop(scenario_id, None)
