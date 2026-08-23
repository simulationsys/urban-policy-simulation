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
    bike_share = "bike_share"
    e_rickshaw = "e_rickshaw"


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
    population: int = Field(default=5_000, ge=1, le=200_000)
    seed: int = Field(default=42, description="Single RNG seed for the whole run.")
    tick_minutes: int = Field(default=5, description="Simulated minutes per tick.")
    max_tracked_agents: int = Field(
        default=2_000,
        ge=1,
        description=(
            "Upper bound on agents streamed individually to the map. Everyone else still "
            "affects the simulation and shows up in the aggregate grid; this only caps how "
            "many are drawn as their own person."
        ),
    )
    start_time_minutes: int = Field(
        default=0,
        ge=0,
        lt=24 * 60,
        description=(
            "Minutes past midnight the run begins at. A run starting at 00:00 shows an "
            "empty city until the morning peak, so demos start in the small hours of the "
            "commute instead of waiting through the night."
        ),
    )
    # Widened to match Event.payload so bool toggles (WFH) and named knobs (metro line) fit.
    params: dict[str, float | int | str | bool] = Field(default_factory=dict)
    # --- Real data mode (Phase 1) ---
    use_real_data: bool = Field(
        default=False,
        description="If true, the sim loads real OSM/transit/population data; "
        "else it uses the synthetic grid fallback.",
    )
    network_paths: dict[str, str] = Field(
        default_factory=dict,
        description="Paths to data files: 'graphml', 'metro_json', 'bus_json'.",
    )
    population_path: str | None = Field(
        default=None,
        description="Path to synthetic_population.parquet for pre-generated agents.",
    )


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
    bus_load_pct: float = 0.0
    road_congestion_index: float = 0.0
    agents_commuting: int = 0
    aqi_estimate: float = Field(
        0.0, ge=0.0, le=500.0, description="Estimated AQI (0-500) from mode-share emissions."
    )
    special_agents: list[dict] = Field(
        default_factory=list,
        description=(
            "Locations and states of special agents "
            "(officers, drainage, police, stalls, stores)."
        ),
    )


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


class AgentLeg(BaseModel):
    """One sampled agent's current journey leg, for map rendering.

    We stream *legs*, not per-tick positions. A tick is several simulated minutes, so a
    position update per tick would teleport a car hundreds of metres; instead the client
    receives the whole leg once and animates along ``polyline`` between ``start_minute``
    and ``start_minute + duration_minutes`` of simulated time.

    Only a fixed-size *focus cohort* is ever serialized — never the whole population
    (PROJECT_SPEC §16.1: "don't render every agent"). The grid cells remain the way
    population-scale density reaches the map.
    """

    agent_id: str
    mode: Mode
    occupation: str = ""
    destination_activity: str = ""
    start_minute: int = Field(description="Simulated minutes since midnight at departure.")
    duration_minutes: float = Field(gt=0, description="Engine's estimated travel time.")
    polyline: list[tuple[float, float]] = Field(
        default_factory=list, description="WGS84 [lat, lon] vertices of the routed path."
    )


class Dwelling(BaseModel):
    """The home a citizen can afford, and where it stands.

    Sent once per focus agent (homes do not move) so the map can build the residential
    fabric and let a spectator step inside.
    """

    kind: str = Field(examples=["jhuggi", "chawl_room", "walkup_flat", "apartment", "bungalow"])
    income_bracket: int = Field(ge=1, le=5)
    area_sqm: float = Field(gt=0)
    storeys: int = Field(ge=1)
    rooms: list[str] = Field(default_factory=list)
    lat: float
    lon: float


class AgentPresence(BaseModel):
    """A tracked agent who is *not* travelling — at home, at work, or minding a business.

    Streamed so the city is populated between commutes: without this, agents vanish the
    moment they arrive somewhere and the map looks deserted outside rush hour. Covers both
    citizens and the economic agents (stalls, shops, delivery riders) that make up the
    working city.
    """

    agent_id: str
    place: str = Field(examples=["home", "away", "stall", "store", "depot"])
    activity: str = Field(description="Plain-language description, e.g. 'Cooking dinner'.")
    lat: float
    lon: float
    role: str = Field(
        default="citizen",
        examples=["citizen", "stall_owner", "store_manager", "store_staff", "delivery_rider"],
        description="What this agent does in the city, which decides how it is drawn.",
    )
    detail: dict[str, str] = Field(
        default_factory=dict,
        description="Role-specific facts for the inspector: takings, stock, deliveries.",
    )


class Snapshot(BaseModel):
    """Full world state at a tick. Fetched over REST, not streamed every frame."""

    scenario_id: str
    tick: int
    sim_time_minutes: int
    status: ScenarioStatus
    metrics: AggregateMetrics
    grid: list[GridCell] = Field(default_factory=list)
    agent_legs: list[AgentLeg] = Field(
        default_factory=list, description="All in-progress legs of the focus cohort."
    )
    presences: list[AgentPresence] = Field(
        default_factory=list, description="Focus-cohort citizens currently stationary."
    )
    dwellings: dict[str, Dwelling] = Field(
        default_factory=dict, description="Focus-cohort homes, keyed by agent id."
    )


class TickDiff(BaseModel):
    """The smallest thing that conveys change — streamed over WebSocket each tick.

    Carries metrics every tick (cheap), only changed grid cells, and only the focus-cohort
    legs that *started* this tick (plus the ids of those that ended).
    """

    scenario_id: str
    tick: int
    metrics: AggregateMetrics
    changed_cells: list[GridCell] = Field(default_factory=list)
    started_legs: list[AgentLeg] = Field(default_factory=list)
    finished_agents: list[str] = Field(default_factory=list)
    presences: list[AgentPresence] = Field(
        default_factory=list, description="Stationary citizens whose activity changed."
    )
    dwellings: dict[str, Dwelling] = Field(
        default_factory=dict, description="Homes not sent to this client yet."
    )


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
