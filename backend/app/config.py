"""Application settings, driven by environment variables.

See ``.env.example`` for the full list. Nothing here calls an external paid API — that is a
hard project constraint (PROJECT_SPEC §4.3).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="BACKEND_",
        extra="ignore",
    )

    # --- HTTP server ---
    host: str = "0.0.0.0"
    port: int = 8000
    environment: str = "development"  # development | production
    api_prefix: str = "/api/v1"

    # CORS: the frontend dev origin(s). Comma-separated env value is split below.
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # --- Simulation engine selection (the seam to SUB-01) ---
    # "fake" -> deterministic stub (app/sim/fake_engine.py), runnable today.
    # "mesa" -> real engine once SUB-01 lands and implements the SimEngine Protocol.
    sim_engine: str = "fake"

    # Wall-clock tick cadence for the live stream (seconds). PROJECT_SPEC target: 1 tick/sec.
    tick_interval_seconds: float = 1.0

    # How many recent snapshots the in-process store keeps per scenario (ring buffer).
    snapshot_buffer_size: int = 2_000

    # --- Metadata persistence (SQLite — NOT Postgres for v1, per PROJECT_SPEC §5.3) ---
    metadata_db_path: str = "data/backend_metadata.sqlite"

    # Default synthetic population size for a new scenario.
    default_population: int = 5_000

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
