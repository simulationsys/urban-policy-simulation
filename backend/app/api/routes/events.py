"""Event injection — user actions become sim events (PROJECT_SPEC §8.3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_scenario_manager, require_scenario
from app.models.schemas import Event, EventAck
from app.services.scenario_manager import ScenarioManager

router = APIRouter(prefix="/scenarios/{scenario_id}", tags=["events"])


@router.post("/events", response_model=EventAck)
def inject_event(
    scenario_id: str,
    event: Event,
    manager: ScenarioManager = Depends(get_scenario_manager),
) -> EventAck:
    """Queue a weather/policy/infrastructure event; applied at the next tick boundary."""
    require_scenario(manager, scenario_id)
    return manager.inject_event(scenario_id, event)
