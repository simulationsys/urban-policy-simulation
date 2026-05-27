"""FastAPI application factory.

Wires the singletons (metadata store, state store, WS manager, scenario manager) into the app
lifespan, mounts the REST routers under ``/api/v1`` and the WebSocket stream under ``/ws``, and
configures CORS for the frontend dev origins. The OpenAPI spec is generated automatically at
``/openapi.json`` (docs at ``/docs``) — that is the API contract the frontend consumes (ROLE_5).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import events, health, metrics, scenarios, snapshots
from app.config import get_settings
from app.services.scenario_manager import ScenarioManager
from app.store.metadata import MetadataStore
from app.store.state import StateStore
from app.ws import stream
from app.ws.manager import ConnectionManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    metadata = MetadataStore(settings.metadata_db_path)
    state = StateStore(settings.snapshot_buffer_size)
    ws_manager = ConnectionManager()
    scenario_manager = ScenarioManager(settings, metadata, state, ws_manager)

    app.state.settings = settings
    app.state.metadata = metadata
    app.state.state_store = state
    app.state.ws_manager = ws_manager
    app.state.scenario_manager = scenario_manager

    logging.getLogger(__name__).info(
        "Backend up: engine=%s, tick=%.2fs", settings.sim_engine, settings.tick_interval_seconds
    )
    try:
        yield
    finally:
        await scenario_manager.shutdown()
        metadata.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Urban Intelligence Platform — Backend (SUB-05)",
        version=__version__,
        description="REST + WebSocket layer between the simulation core and the dashboard.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health endpoints are unprefixed so probes/smoke tests hit /healthz directly.
    app.include_router(health.router)

    # Versioned REST API.
    api = settings.api_prefix
    app.include_router(scenarios.router, prefix=api)
    app.include_router(snapshots.router, prefix=api)
    app.include_router(metrics.router, prefix=api)
    app.include_router(events.router, prefix=api)

    # WebSocket stream (not versioned via prefix; path carries /ws).
    app.include_router(stream.router)

    return app


app = create_app()
