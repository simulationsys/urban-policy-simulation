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
from app.models.schemas import ScenarioConfig, ScenarioStatus
from app.services.scenario_manager import ScenarioManager
from app.store.metadata import MetadataStore
from app.store.state import StateStore
from app.ws import stream
from app.ws.manager import ConnectionManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


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

    # Engines live in this process only, so a row still marked "running" from a previous
    # boot is stale. Reconcile it to paused rather than letting clients believe a tick loop
    # is alive (and re-start it behind the user's back).
    if settings.environment != "test":
        for stale in metadata.list():
            if stale.status is ScenarioStatus.running:
                metadata.update_status(stale.id, ScenarioStatus.paused)
                logger.info("Marked stale running scenario %s as paused on boot", stale.id)

    # Auto-populate default scenarios if empty (allows frontend to connect immediately).
    # They opt into real street data whenever it is present, otherwise every default run
    # would sit on the synthetic grid and the map would show citizens cutting across blocks.
    if settings.environment != "test":
        real_data = settings.real_data_available()
        try:
            if not metadata.list():
                for name in (
                    "scenario_a_monsoon",
                    "scenario_b_metro_shutdown",
                    "scenario_c_fuel_shock",
                ):
                    scenario_manager.create(
                        ScenarioConfig(
                            name=name,
                            city="delhi",
                            population=settings.default_population,
                            seed=42,
                            use_real_data=real_data,
                            # 06:30 — households are stirring and the peak is minutes away,
                            # so the map has life the moment someone opens it.
                            start_time_minutes=390,
                        )
                    )
                logger.info(
                    "Pre-populated default scenarios (use_real_data=%s)", real_data
                )
        except Exception as e:
            logger.warning("Failed to pre-populate default scenarios: %s", e)

    engine_kind, engine_reason = settings.resolve_engine_kind()
    logger.info(
        "Backend up: engine=%s (%s), tick=%.2fs",
        engine_kind,
        engine_reason,
        settings.tick_interval_seconds,
    )
    if engine_kind == "fake":
        logger.warning(
            "Serving the STUB engine: metrics are analytic and no individual citizens are "
            "simulated, so the map will fall back to canned demo routes."
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

    origins = settings.cors_origin_list
    allow_origins = ["*"] if "*" in origins or not origins else origins

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True if allow_origins != ["*"] else False,
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
