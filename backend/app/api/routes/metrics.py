"""Aggregate metric time series for charts (REST)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_scenario_manager, require_scenario
from app.models.schemas import MetricSeries
from app.services.scenario_manager import ScenarioManager

router = APIRouter(prefix="/scenarios/{scenario_id}", tags=["metrics"])


@router.get("/metrics", response_model=MetricSeries)
def metric_series(
    scenario_id: str,
    from_tick: int = Query(0, ge=0),
    to_tick: int = Query(10**9, ge=0),
    manager: ScenarioManager = Depends(get_scenario_manager),
) -> MetricSeries:
    """Per-tick aggregates within ``[from_tick, to_tick]`` from the in-process buffer."""
    require_scenario(manager, scenario_id)
    state = manager._state.get(scenario_id)  # noqa: SLF001 - internal store access by owner
    points = state.metric_window(from_tick, to_tick) if state else []
    return MetricSeries(
        scenario_id=scenario_id,
        from_tick=from_tick,
        to_tick=to_tick,
        points=points,
    )
