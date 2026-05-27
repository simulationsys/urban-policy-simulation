"""Health & readiness — the daily integration smoke test targets these (ROLE_5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app import __version__
from app.api.deps import get_scenario_manager
from app.services.scenario_manager import ScenarioManager

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness: the process is up."""
    return {"status": "ok", "version": __version__}


@router.get("/readyz")
def readyz(manager: ScenarioManager = Depends(get_scenario_manager)) -> dict[str, object]:
    """Readiness: dependencies (metadata store, engine factory) are wired."""
    return {"status": "ready", "scenarios": len(manager.list())}
