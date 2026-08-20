"""Application settings, driven by environment variables.

See ``.env.example`` for the full list. Nothing here calls an external paid API — that is a
hard project constraint (PROJECT_SPEC §4.3).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from app.sim.adapter import DataPaths


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
    # "auto" -> use the real Mesa engine when it can actually run here, else the stub.
    # "fake" -> deterministic stub (app/sim/fake_engine.py).
    # "mesa" -> force the real engine; fails loudly if its imports are unavailable.
    #
    # "auto" is the default because the failure mode of a silent "fake" is the worst one we
    # have: the API keeps streaming plausible metrics, the map falls back to canned routes,
    # and it looks like a working city simulation when no citizen is being simulated.
    sim_engine: str = "auto"

    # Wall-clock tick cadence for the live stream (seconds). PROJECT_SPEC target: 1 tick/sec.
    tick_interval_seconds: float = 1.0

    # How many recent snapshots the in-process store keeps per scenario (ring buffer).
    snapshot_buffer_size: int = 2_000

    # --- Metadata persistence (SQLite — NOT Postgres for v1, per PROJECT_SPEC §5.3) ---
    metadata_db_path: str = "data/backend_metadata.sqlite"

    # Default synthetic population size for a new scenario.
    default_population: int = 5_000

    # --- Real-data inputs (SUB-04 outputs; loaded by the mesa engine) ---
    processed_data_dir: str = "data/processed_data"

    def resolved_processed_dir(self) -> Path:
        """Absolute location of the processed-data directory.

        The default is repo-relative, but the documented way to run the server is
        ``cd backend && uvicorn app.main:app`` — so resolving against the working directory
        alone silently looked inside ``backend/`` and reported the real street data as
        missing. Try the working directory first (an explicit relative override should still
        win), then the repository root.
        """
        configured = Path(self.processed_data_dir)
        if configured.is_absolute():
            return configured

        repo_root = Path(__file__).resolve().parents[2]
        for candidate in (Path.cwd() / configured, repo_root / configured):
            if candidate.exists():
                return candidate
        return Path.cwd() / configured

    def resolved_data_paths(self, city: str) -> DataPaths:
        """Map config intent → concrete files under processed_data_dir.

        Fails fast (at scenario creation) if a required file is missing, so the
        error surfaces cleanly instead of crashing mid tick-loop.
        """
        from app.sim.adapter import DataPaths  # local import avoids any cycle

        base = self.resolved_processed_dir()
        paths = DataPaths(
            road_network=base / "network.graphml",
            metro_network=base / "metro_network.json",
            bus_routes=base / "bus_routes.json",
            population=base / "synthetic_population.parquet",  # TODO(SUB-04): confirm filename
            weather=base / f"weather_{city}.csv",
        )
        missing = [str(p) for p in paths.required() if not p.exists()]
        if missing:
            raise FileNotFoundError(
                "use_real_data=True but these processed-data files are missing: "
                + ", ".join(missing)
            )
        return paths

    def real_data_available(self, city: str = "delhi") -> bool:
        """True when the processed inputs a real-data run needs are on disk."""
        try:
            self.resolved_data_paths(city)
            return True
        except FileNotFoundError:
            return False

    def resolve_engine_kind(self) -> tuple[str, str]:
        """Decide which engine to build, and say why.

        Returns ``(kind, reason)``. The reason is logged at boot so it is obvious from the
        server output whether real citizens are being simulated.
        """
        if self.sim_engine != "auto":
            return self.sim_engine, f"BACKEND_SIM_ENGINE={self.sim_engine}"

        importable, problem = _mesa_engine_importable()
        if not importable:
            return "fake", f"real engine unavailable: {problem}"

        if not self.real_data_available():
            return (
                "mesa",
                "real engine on the synthetic grid - no processed data in "
                f"{self.resolved_processed_dir()} (run data/pipelines/run_all.py to "
                "route citizens along real streets)",
            )
        return "mesa", f"real engine on real street data from {self.resolved_processed_dir()}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def _mesa_engine_importable() -> tuple[bool, str]:
    """Can the real engine actually be constructed in this process?

    Locating the module is not enough — it pulls in mesa, networkx, pandas and pyarrow, any
    of which may be absent in a slim deployment. Import it for real, once, so the boot log
    reflects what will actually happen rather than what ought to.
    """
    try:
        import simulation.engine  # noqa: F401
    except ImportError as exc:
        return False, f"{exc.__class__.__name__}: {exc}"
    except Exception as exc:  # pragma: no cover - defensive
        return False, f"failed to import simulation.engine ({exc})"
    return True, ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
