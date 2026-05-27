"""Scenario CRUD + lifecycle (start / pause / resume / reset / branch)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import get_scenario_manager, require_scenario
from app.models.schemas import (
    BranchScenarioRequest,
    CreateScenarioRequest,
    ScenarioSummary,
)
from app.services.scenario_manager import ScenarioManager

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("", response_model=list[ScenarioSummary])
def list_scenarios(
    manager: ScenarioManager = Depends(get_scenario_manager),
) -> list[ScenarioSummary]:
    return manager.list()


@router.post("", response_model=ScenarioSummary, status_code=status.HTTP_201_CREATED)
def create_scenario(
    body: CreateScenarioRequest, manager: ScenarioManager = Depends(get_scenario_manager)
) -> ScenarioSummary:
    return manager.create(body.config)


@router.get("/{scenario_id}", response_model=ScenarioSummary)
def get_scenario(
    scenario_id: str, manager: ScenarioManager = Depends(get_scenario_manager)
) -> ScenarioSummary:
    return require_scenario(manager, scenario_id)


# Lifecycle handlers are async so create_task/cancel run on the event loop, not a threadpool.
@router.post("/{scenario_id}/start", response_model=ScenarioSummary)
async def start_scenario(
    scenario_id: str, manager: ScenarioManager = Depends(get_scenario_manager)
) -> ScenarioSummary:
    require_scenario(manager, scenario_id)
    return manager.start(scenario_id)


@router.post("/{scenario_id}/pause", response_model=ScenarioSummary)
async def pause_scenario(
    scenario_id: str, manager: ScenarioManager = Depends(get_scenario_manager)
) -> ScenarioSummary:
    require_scenario(manager, scenario_id)
    return manager.pause(scenario_id)


@router.post("/{scenario_id}/resume", response_model=ScenarioSummary)
async def resume_scenario(
    scenario_id: str, manager: ScenarioManager = Depends(get_scenario_manager)
) -> ScenarioSummary:
    require_scenario(manager, scenario_id)
    return manager.resume(scenario_id)


@router.post("/{scenario_id}/reset", response_model=ScenarioSummary)
async def reset_scenario(
    scenario_id: str, manager: ScenarioManager = Depends(get_scenario_manager)
) -> ScenarioSummary:
    require_scenario(manager, scenario_id)
    return manager.reset(scenario_id)


@router.post(
    "/{scenario_id}/branch",
    response_model=ScenarioSummary,
    status_code=status.HTTP_201_CREATED,
)
def branch_scenario(
    scenario_id: str,
    body: BranchScenarioRequest,
    manager: ScenarioManager = Depends(get_scenario_manager),
) -> ScenarioSummary:
    require_scenario(manager, scenario_id)
    return manager.branch(scenario_id, body.name)


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(
    scenario_id: str, manager: ScenarioManager = Depends(get_scenario_manager)
) -> None:
    require_scenario(manager, scenario_id)
    manager.delete(scenario_id)
