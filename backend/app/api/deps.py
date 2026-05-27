"""Shared FastAPI dependencies.

Singletons (state store, metadata store, scenario manager, WS manager) are created once in the app
lifespan and stashed on ``app.state``; these helpers expose them to routes via DI.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from app.services.scenario_manager import ScenarioManager
from app.ws.manager import ConnectionManager


def get_scenario_manager(request: Request) -> ScenarioManager:
    return request.app.state.scenario_manager


def get_ws_manager(request: Request) -> ConnectionManager:
    return request.app.state.ws_manager


def require_scenario(manager: ScenarioManager, scenario_id: str):
    summary = manager.get(scenario_id)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id!r} not found")
    return summary
