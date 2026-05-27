"""Snapshot fetch — full world state over REST (not streamed every frame)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_scenario_manager, require_scenario
from app.models.schemas import Snapshot
from app.services.scenario_manager import ScenarioManager

router = APIRouter(prefix="/scenarios/{scenario_id}", tags=["snapshots"])


@router.get("/snapshot", response_model=Snapshot)
def current_snapshot(
    scenario_id: str, manager: ScenarioManager = Depends(get_scenario_manager)
) -> Snapshot:
    """Latest full snapshot (tick-0 if the run hasn't started)."""
    require_scenario(manager, scenario_id)
    return manager.current_snapshot(scenario_id)


@router.get("/snapshot/{tick}", response_model=Snapshot)
def snapshot_at_tick(
    scenario_id: str, tick: int, manager: ScenarioManager = Depends(get_scenario_manager)
) -> Snapshot:
    """A specific historical snapshot, if still in the in-process buffer."""
    require_scenario(manager, scenario_id)
    state = manager._state.get(scenario_id)  # noqa: SLF001 - internal store access by owner
    snap = state.snapshot_at(tick) if state else None
    if snap is None:
        raise HTTPException(
            status_code=404,
            detail=f"Tick {tick} not in buffer (aged out; long history lives in Parquet)",
        )
    return snap
