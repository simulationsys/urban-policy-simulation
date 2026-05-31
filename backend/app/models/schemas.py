"""Wire contracts — the API contract lives here.

Every shape the frontend (SUB-06) or sim core (SUB-01) depends on is a Pydantic model in this
module. Treat changes here as contract changes: coordinate with the producer (SUB-01) and the
consumer (SUB-06), and version the API if you must break a field (PROJECT_SPEC §15, ROLE_5).

Conventions (PROJECT_SPEC §15.2):
- IDs are stable strings (``scenario_0001``).
- Monetary values are integer **paise**; the frontend formats ₹.
- Coordinates are WGS84 lat/lon.
- A run is fully described by ``config + seed`` (determinism).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------------------
class Mode(StrEnum):
    walk = "walk"
    bike = "bike"
    bus = "bus"
    metro = "metro"
    auto = "auto"
    car = "car"


class ScenarioStatus(StrEnum):
    created = "created"
    running = "running"
    paused = "paused"
    finished = "finished"
    error = "error"


class EventType(StrEnum):
    weather = "WEATHER_EVENT"
    policy = "POLICY_EVENT"
    infrastructure = "INFRASTRUCTURE_EVENT"


# --------------------------------------------------------------------------------------
# Scenario configuration & lifecycle
# --------------------------------------------------------------------------------------
class ScenarioConfig(BaseModel):
    """Inputs that, together with a seed, reproduce a run exactly."""

    name: str = Field(examples=["scenario_a_monsoon"])
    city: str = Field(default="delhi", description="Chosen city; see PROJECT_SPEC §18.")
    population: int = Field(default=10_000, ge=1, le=200_000)
    seed: int = Field(default=42, description="Single RNG seed for the whole run.")
    tick_minutes: int = Field(default=5, description="Simulated minutes per tick.")
    # Free-form initial policy/environment knobs (validated by the sim layer, not here).
    params: dict[str, float] = Field(default_factory=dict)


class ScenarioSummary(BaseModel):
    """Lightweight scenario record returned by list/detail endpoints."""

    id: str
    name: str
    status: ScenarioStatus
    config: ScenarioConfig
    current_tick: int = 0
    created_at: datetime
    updated_at: datetime


class CreateScenarioRequest(BaseModel):
    config: ScenarioConfig


class BranchScenarioRequest(BaseModel):
    """Fork a scenario at its current tick into a new independent run."""

    name: str


# --------------------------------------------------------------------------------------
# Events (frontend -> backend -> sim)
# --------------------------------------------------------------------------------------
class Event(BaseModel):
    """A policy/weather/infra event injected at the next tick boundary (PROJECT_SPEC §8.3)."""

    type: EventType
    # Examples:
    #   WEATHER_EVENT       -> {"rain_intensity": 0.8, "duration_ticks": 60}
    #   POLICY_EVENT        -> {"bus_capacity_pct": 1.2} or {"fuel_price_delta_paise": 2000}
    #   INFRASTRUCTURE_EVENT-> {"disable_metro_line": "yellow"}
    payload: dict[str, float | int | str | bool]


class EventAck(BaseModel):
    accepted: bool
    scenario_id: str
    queued_for_tick: int
    event: Event


# --------------------------------------------------------------------------------------
# Aggregate metrics (REST history + streamed each tick)
# --------------------------------------------------------------------------------------
class AggregateMetrics(BaseModel):
    """Per-tick aggregates. Small enough to stream every tick."""

    tick: int
    sim_time_minutes: int
    rain_intensity: float = Field(0.0, ge=0.0, le=1.0)
    avg_commute_minutes: float = 0.0
    mode_share: dict[Mode, float] = Field(default_factory=dict)
    metro_load_pct: float = 0.0
    road_congestion_index: float = 0.0
    agents_commuting: int = 0


class MetricSeries(BaseModel):
    """A time series of one or more aggregate metrics for charting (REST)."""

    scenario_id: str
    from_tick: int
    to_tick: int
    points: list[AggregateMetrics]


# --------------------------------------------------------------------------------------
# Snapshots (full state via REST; diffs via WebSocket)
# --------------------------------------------------------------------------------------
class GridCell(BaseModel):
    """Aggregated map cell — we never serialize every agent (ROLE_5 anti-pattern)."""

    lat: float
    lon: float
    density: int = 0
    congestion: float = 0.0


class Snapshot(BaseModel):
    """Full world state at a tick. Fetched over REST, not streamed every frame."""

    scenario_id: str
    tick: int
    sim_time_minutes: int
    status: ScenarioStatus
    metrics: AggregateMetrics
    grid: list[GridCell] = Field(default_factory=list)


class TickDiff(BaseModel):
    """The smallest thing that conveys change — streamed over WebSocket each tick.

    Carries metrics every tick (cheap) and only changed grid cells.
    """

    scenario_id: str
    tick: int
    metrics: AggregateMetrics
    changed_cells: list[GridCell] = Field(default_factory=list)


# --------------------------------------------------------------------------------------
# WebSocket envelope
# --------------------------------------------------------------------------------------
class WSMessageType(StrEnum):
    tick = "tick"
    status = "status"
    error = "error"


class WSMessage(BaseModel):
    """Envelope for every WebSocket frame so the client can switch on ``type``."""

    type: WSMessageType
    scenario_id: str
    tick: int | None = None
    diff: TickDiff | None = None
    status: ScenarioStatus | None = None
    message: str | None = None
