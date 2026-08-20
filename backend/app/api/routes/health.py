"""Health & readiness — the daily integration smoke test targets these (ROLE_5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app import __version__
from app.api.deps import get_scenario_manager
from app.config import get_settings
from app.services.scenario_manager import ScenarioManager

router = APIRouter(tags=["health"])


@router.get("/")
def root() -> dict[str, object]:
    """Friendly landing — silences the 'GET / 404' a browser auto-fires.

    This is an API, not a website, but operators who hit the bare host shouldn't
    have to guess what to open next. Lists the entry points and the version.
    """
    return {
        "service": "Urban Intelligence Platform — Backend (SUB-05)",
        "version": __version__,
        "links": {
            "docs": "/docs",
            "openapi": "/openapi.json",
            "healthz": "/healthz",
            "readyz": "/readyz",
            "scenarios": "/api/v1/scenarios",
        },
    }


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness: the process is up."""
    return {"status": "ok", "version": __version__}


@router.get("/readyz")
def readyz(manager: ScenarioManager = Depends(get_scenario_manager)) -> dict[str, object]:
    """Readiness: dependencies (metadata store, engine factory) are wired.

    Reports which engine is actually live. The dashboard reads this so it can say plainly
    whether you are watching simulated citizens or the canned demo routes — the two look
    similar on a map and must never be confused.
    """
    settings = get_settings()
    kind, reason = settings.resolve_engine_kind()
    return {
        "status": "ready",
        "scenarios": len(manager.list()),
        "engine": kind,
        "engine_reason": reason,
        "real_data": settings.real_data_available(),
        "simulates_individuals": kind == "mesa",
    }
