"""Scenario CRUD + lifecycle (start / pause / resume / reset / branch)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_scenario_manager, require_scenario
from app.models.schemas import (
    BranchScenarioRequest,
    CreateScenarioRequest,
    ScenarioSummary,
)
from app.services.scenario_manager import ScenarioManager

logger = logging.getLogger(__name__)

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
    try:
        return manager.create(body.config)
    except FileNotFoundError as exc:
        logger.warning("Scenario create failed — missing data files: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


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
    try:
        return manager.branch(scenario_id, body.name)
    except FileNotFoundError as exc:
        logger.warning("Scenario branch failed — missing data files: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


# response_model=None is required: with `from __future__ import annotations` the `-> None`
# return annotation reaches FastAPI as a type it treats as a response body, which a 204
# must not have.
@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_scenario(
    scenario_id: str, manager: ScenarioManager = Depends(get_scenario_manager)
) -> None:
    require_scenario(manager, scenario_id)
    manager.delete(scenario_id)
