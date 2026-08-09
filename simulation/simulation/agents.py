"""Citizen Agent representation and behavior.

Defines the Agent properties, decision functions (utility model),
schedules, memory, and state transitions.

Integrates advanced features from SUB-02 (Agent Behavior / AI):
- 5 Indian occupational archetypes with per-occupation utility weights
- Household car-sharing mutex
- Multi-leg activity schedules (Home→School→Work→Shopping→Home)
- Frustration-driven mode switching
- Structured AgentMemory with per-mode rolling history
"""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

import mesa
import numpy as np

if TYPE_CHECKING:
    from simulation.engine import UrbanModel
    from simulation.network import MultiModalNetwork


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Mode(str, Enum):
    """Transport modes available in the simulation."""

    WALK = "walk"
    BIKE = "bike"
    BUS = "bus"
    METRO = "metro"
    AUTO = "auto"
    CAR = "car"
    BIKE_SHARE = "bike_share"
    E_RICKSHAW = "e_rickshaw"


class Occupation(str, Enum):
    """Indian occupational archetypes — drives schedule, weights, and behavior."""

    OFFICE_EXECUTIVE = "office_executive"
    STUDENT = "student"
    BLUE_COLLAR_WORKER = "blue_collar_worker"
    GIG_WORKER = "gig_worker"
    RETIRED_CITIZEN = "retired_citizen"
    STALL_OWNER = "stall_owner"
    STORE_MANAGER = "store_manager"
    STORE_STAFF = "store_staff"
    UNEMPLOYED = "unemployed"


class ActivityType(str, Enum):
    """Types of activities in an agent's daily schedule."""

    HOME = "home"
    WORK = "work"
    EDUCATION = "education"
    SHOPPING = "shopping"
    RECREATION = "recreation"
    GIG_WORK = "gig_work"
    ESCORTING = "escorting"
    VENDING = "vending"


class AgentState:
    AT_HOME = "AT_HOME"
    DEPARTING = "DEPARTING"
    COMMUTING = "COMMUTING"
    AT_WORK = "AT_WORK"
    RETURNING = "RETURNING"


# ---------------------------------------------------------------------------
# Activity Schedule — multi-leg daily tours
# ---------------------------------------------------------------------------


@dataclass
class Activity:
    """A single activity in the agent's daily schedule."""

    activity_type: ActivityType
    location_node: str  # node ID in the network graph
    start_time_min: int  # minutes since midnight
    duration_min: int  # minutes


@dataclass
class ActivitySchedule:
    """Stylised daily schedule. Supports multiple activities (multi-leg tours).

    Example: Home→Escort(school)→Work→Shopping→Home
    """

    activities: list[Activity] = field(default_factory=list)
    leave_home_min: int = 9 * 60  # 09:00
    leave_home_jitter: int = 30
    work_duration_min: int = 8 * 60  # 8h
    return_jitter: int = 45
    discretionary_evening_prob: float = 0.1

    def get_legs(self) -> list[tuple[Activity, Activity]]:
        """Returns a list of legs as (origin_activity, destination_activity) pairs.

        Assumes the first activity is home, and it loops back to home if not ended at home.
        """
        if not self.activities:
            return []
        legs = []
        for i in range(len(self.activities) - 1):
            legs.append((self.activities[i], self.activities[i + 1]))
        if self.activities[-1].activity_type != ActivityType.HOME:
            legs.append((self.activities[-1], self.activities[0]))
        return legs

    def return_home_min(self) -> int:
        """Helper to retrieve the time the agent should start returning home."""
        if not self.activities:
            return self.leave_home_min + self.work_duration_min

        work_act = next(
            (a for a in self.activities if a.activity_type == ActivityType.WORK), None
        )
        if work_act:
            return work_act.start_time_min + work_act.duration_min

        last_non_home = [
            a for a in self.activities if a.activity_type != ActivityType.HOME
        ]
        if last_non_home:
            return last_non_home[-1].start_time_min + last_non_home[-1].duration_min
        return self.leave_home_min + self.work_duration_min


# ---------------------------------------------------------------------------
# Household — car-sharing mutex
# ---------------------------------------------------------------------------


@dataclass
class Household:
    """Represents a family or co-living unit sharing resources.

    Implements a car-sharing mutex: household members must request_car()
    before driving and release_car() when done commuting.
    """

    id: int
    member_ids: list[int] = field(default_factory=list)
    has_car: bool = False
    cars_owned: int = 0
    cars_available: int = 0

    def reset_daily_resources(self) -> None:
        """Reset shared resources at the beginning of each day."""
        self.cars_available = self.cars_owned

    def request_car(self) -> bool:
        """Attempt to claim a car for a commute. Returns True if successful."""
        if self.cars_available > 0:
            self.cars_available -= 1
            return True
        return False

    def release_car(self) -> None:
        """Return a car to the household resource pool."""
        if self.cars_available < self.cars_owned:
            self.cars_available += 1


# ---------------------------------------------------------------------------
# Agent Memory — per-mode rolling history with frustration tracking
# ---------------------------------------------------------------------------


@dataclass
class CommuteOutcome:
    """Structured record of a single commute outcome."""

    mode: str
    travel_time_min: float
    monetary_cost: float = 0.0
    comfort_score: float = 0.5  # 0..1; higher = more comfortable


@dataclass
class AgentMemory:
    """Per-agent rolling memory of recent commute outcomes per mode.

    Tracks frustration: if a commute is 25%+ slower than the rolling average
    for that mode, frustration increases. Otherwise it cools down.
    """

    window: int = 10
    by_mode: dict[str, deque] = field(default_factory=dict)
    frustration_by_mode: dict[str, float] = field(default_factory=dict)

    def record(self, outcome: CommuteOutcome) -> None:
        """Record a commute outcome and update frustration tracking."""
        buf = self.by_mode.setdefault(outcome.mode, deque(maxlen=self.window))

        # Calculate moving average before adding the new outcome
        old_avg = None
        if len(buf) >= 2:
            old_avg = sum(o.travel_time_min for o in buf) / len(buf)

        buf.append(outcome)

        # Update frustration
        if old_avg is not None and outcome.travel_time_min > old_avg * 1.25:
            # 25% or more above average commute time -> increase frustration
            self.frustration_by_mode[outcome.mode] = min(
                3.0, self.frustration_by_mode.get(outcome.mode, 0.0) + 1.0
            )
        else:
            # Normal or good commute -> cool down frustration by 0.5
            self.frustration_by_mode[outcome.mode] = max(
                0.0, self.frustration_by_mode.get(outcome.mode, 0.0) - 0.5
            )

    def avg_time(self, mode: str) -> float | None:
        """Return average travel time for a mode, or None if no history."""
        buf = self.by_mode.get(mode)
        if not buf:
            return None
        return sum(o.travel_time_min for o in buf) / len(buf)

    def get_frustration(self, mode: str) -> float:
        """Return current frustration level for a mode (0.0 to 3.0)."""
        return self.frustration_by_mode.get(mode, 0.0)

    def habit_bonus(self, mode: str) -> float:
        """Fraction of recent trips taken on this mode across all modes seen."""
        total = sum(len(b) for b in self.by_mode.values())
        if total == 0:
            return 0.0
        return len(self.by_mode.get(mode, ())) / total

    @property
    def last_outcome(self) -> CommuteOutcome | None:
        """Return the most recent commute outcome across all modes."""
        latest = None
        for buf in self.by_mode.values():
            if buf:
                candidate = buf[-1]
                if latest is None:
                    latest = candidate
                # We just return any recent one — no timestamp to compare
        # Fallback: check all buffers and return the last appended
        all_outcomes = []
        for buf in self.by_mode.values():
            all_outcomes.extend(buf)
        return all_outcomes[-1] if all_outcomes else None


# ---------------------------------------------------------------------------
# Utility Weights — per-occupation archetypes
# ---------------------------------------------------------------------------


@dataclass
class UtilityWeights:
    """Per-agent (or default) mode-choice utility coefficients.

    Each occupation archetype has distinct behavioral preferences:
    - Office executives: time-sensitive, comfort-loving, cost-insensitive
    - Students: cost-sensitive, weather-vulnerable
    - Blue-collar workers: balanced, habit-driven
    - Gig workers: extremely time-sensitive (earnings depend on speed)
    - Retired citizens: comfort and weather dominant, unhurried
    """

    beta_time: float = -0.08  # per minute
    beta_cost: float = -0.02  # per ₹ (further scaled by income inside the model)
    beta_comfort: float = 0.5
    beta_weather: float = -1.5
    beta_habit: float = 0.4

    @staticmethod
    def for_occupation(occupation: Occupation) -> UtilityWeights:
        """Return archetype-specific utility weights.

        Calibrated against Delhi 2018 mode share survey (RITES):
        Metro 15.5%, Bus 18%, Two-Wheeler 28.5%, Car 12%, Walk/Auto 26%.
        """
        if occupation == Occupation.OFFICE_EXECUTIVE:
            return UtilityWeights(
                beta_time=-0.15,
                beta_cost=-0.012,  # raised from -0.002 to penalise car cost
                beta_comfort=1.8,
                beta_weather=-0.4,
                beta_habit=0.4,
            )
        elif occupation == Occupation.STUDENT:
            return UtilityWeights(
                beta_time=-0.04,
                beta_cost=-0.06,  # slightly lowered from -0.08
                beta_comfort=0.1,
                beta_weather=-1.5,
                beta_habit=0.3,
            )
        elif occupation == Occupation.BLUE_COLLAR_WORKER:
            return UtilityWeights(
                beta_time=-0.10,
                beta_cost=-0.04,  # slightly lowered from -0.05
                beta_comfort=0.2,
                beta_weather=-1.2,
                beta_habit=0.5,
            )
        elif occupation == Occupation.GIG_WORKER:
            return UtilityWeights(
                beta_time=-0.18,
                beta_cost=-0.05,  # slightly lowered from -0.06
                beta_comfort=0.1,
                beta_weather=-1.0,
                beta_habit=0.2,
            )
        elif occupation == Occupation.RETIRED_CITIZEN:
            return UtilityWeights(
                beta_time=-0.03,
                beta_cost=-0.025,  # slightly lowered from -0.03
                beta_comfort=1.2,
                beta_weather=-2.5,
                beta_habit=0.6,
            )
        return UtilityWeights()


# ---------------------------------------------------------------------------
# Mode Choice Model — MNL with Gumbel noise & frustration
# ---------------------------------------------------------------------------

# Per-km rough estimates: (minutes/km, ₹/km, comfort 0..1)
# Calibrated to Delhi 2018 mode share targets (RITES survey).
_MODE_PROFILE: dict[str, tuple[float, float, float]] = {
    "walk": (12.0, 0.0, 0.30),
    "bike": (4.0, 0.5, 0.40),
    "bus": (
        5.0,
        1.2,
        0.55,
    ),  # lowered cost ₹1.5→₹1.2, raised comfort 0.45→0.55 (DTC subsidy)
    "metro": (3.0, 2.5, 0.65),  # lowered cost ₹3→₹2.5 (DMRC subsidised)
    "auto": (3.5, 12.0, 0.55),
    "car": (3.0, 10.0, 0.75),  # raised cost ₹8→₹10 (fuel + parking in central Delhi)
    "bike_share": (
        4.5,
        1.0,
        0.35,
    ),  # slightly slower than owned bike, ₹1/km (docking time)
    "e_rickshaw": (5.0, 4.0, 0.50),  # ~12 km/h, ₹4/km, moderate comfort
}

# How exposed each mode is to rain (0 = sheltered, 1 = fully exposed).
_RAIN_EXPOSURE: dict[str, float] = {
    "walk": 1.0,
    "bike": 1.0,
    "auto": 0.5,
    "bus": 0.2,
    "metro": 0.0,
    "car": 0.0,
    "bike_share": 1.0,  # fully exposed
    "e_rickshaw": 0.6,  # partially covered
}


@dataclass
class ModeAlternative:
    """A single candidate mode with estimated travel attributes."""

    mode: str
    travel_time_min: float
    monetary_cost: float
    comfort_score: float  # 0..1
    weather_penalty: float = 0.0  # 0..1; higher when rain + exposed mode


class ModeChoiceModel:
    """Multinomial Logit mode choice with Gumbel noise sampling.

    U(mode) = β_time*time + β_cost*cost + β_comfort*comfort
              + β_weather*weather_penalty + β_habit*habit_bonus
              - frustration*0.8 + ε
    """

    def __init__(
        self,
        weights: UtilityWeights | None = None,
        rng: np.random.Generator | None = None,
    ):
        self.w = weights or UtilityWeights()
        self.rng = rng or np.random.default_rng()

    # Non-linear income-stratified cost sensitivity (PRD §4, SUB-02, task 2.1).
    # Fuel shocks hit low-income auto/car users much harder than high-income.
    _INCOME_COST_SCALE: dict[int, float] = {
        1: 3.0,   # Lowest income — extremely cost-sensitive
        2: 1.8,   # Low-medium
        3: 0.9,   # Medium
        4: 0.3,   # Medium-high
        5: 0.05,  # Highest income — virtually cost-insensitive
    }

    def utility(self, agent: CitizenAgent, alt: ModeAlternative) -> float:
        """Compute the deterministic utility of a mode alternative for an agent."""
        w = agent.weights or self.w
        # Non-linear income-stratified cost sensitivity (SUB-02, task 2.1).
        # Low-income agents are dramatically more sensitive to cost changes
        # (e.g. fuel shock), while high-income agents are nearly insensitive.
        cost_scale = self._INCOME_COST_SCALE.get(agent.income_bracket, 0.9)
        habit = agent.memory.habit_bonus(alt.mode)
        frustration = agent.memory.get_frustration(alt.mode)
        return (
            w.beta_time * alt.travel_time_min
            + w.beta_cost * cost_scale * alt.monetary_cost
            + w.beta_comfort * alt.comfort_score
            + w.beta_weather * alt.weather_penalty
            + w.beta_habit * habit
            - frustration * 0.8
        )

    def choose(
        self,
        agent: CitizenAgent,
        alts: list[ModeAlternative],
        stochastic: bool = True,
    ) -> str:
        """Select a mode from alternatives using MNL with Gumbel noise."""
        if not alts:
            return "walk"
        utilities = np.array([self.utility(agent, a) for a in alts], dtype=float)
        if stochastic:
            # Gumbel noise → softmax-equivalent sampling (MNL).
            gumbel = self.rng.gumbel(size=utilities.shape)
            idx = int(np.argmax(utilities + gumbel))
        else:
            idx = int(np.argmax(utilities))
        return alts[idx].mode


# ---------------------------------------------------------------------------
# Citizen Agent — the main Mesa agent with all advanced features
# ---------------------------------------------------------------------------


class CitizenAgent(mesa.Agent):
    """An individual citizen agent commuting in the city.

    Advanced features integrated from SUB-02:
    - Occupational archetype with per-occupation utility weights
    - Household car-sharing (must request/release from household pool)
    - Multi-leg activity schedules (not just home↔work)
    - Frustration-driven mode switching via AgentMemory
    """

    def __init__(
        self,
        unique_id: int,
        model: UrbanModel,
        home_node: str,
        work_node: str | None,
        income_bracket: int,  # 1 to 5
        age: int,
        has_car: bool,
        has_bike: bool,
        has_metro_pass: bool,
        # --- Advanced fields from SUB-02 ---
        occupation: Occupation = Occupation.BLUE_COLLAR_WORKER,
        household_id: int = 0,
        household: Household | None = None,
        schedule: ActivitySchedule | None = None,
        weights: UtilityWeights | None = None,
        activity_locations: dict | None = None,
        parent_id: int | None = None,
        child_ids: list[int] | None = None,
    ) -> None:
        super().__init__(model)
        self.unique_id = unique_id
        self.model: UrbanModel = model
        self.home_node = home_node
        self.work_node = work_node
        self.income_bracket = income_bracket
        self.age = age
        self.has_car = has_car
        self.has_bike = has_bike
        self.has_metro_pass = has_metro_pass

        # Advanced agent properties
        self.occupation = occupation
        self.household_id = household_id
        self.household = household
        self.weights = weights
        self.activity_locations = activity_locations or {}
        self.parent_id = parent_id
        self.child_ids = child_ids or []

        # Multi-leg activity schedule
        if schedule is not None:
            self.schedule = schedule
        else:
            # Fallback: simple home→work→home schedule
            self.schedule = ActivitySchedule(
                leave_home_min=480 + random.randint(0, 90),
                work_duration_min=480 + random.randint(-30, 90),
            )
            if work_node:
                self.schedule.activities = [
                    Activity(
                        ActivityType.HOME, home_node, 0, self.schedule.leave_home_min
                    ),
                    Activity(
                        ActivityType.WORK,
                        work_node,
                        self.schedule.leave_home_min,
                        self.schedule.work_duration_min,
                    ),
                ]

        # Track which leg of the schedule we're on
        self._current_leg_index = 0

        # Adaptation adjustments (learned through experience)
        self.departure_adjustment = 0.0

        # Structured memory with frustration tracking
        self.memory = AgentMemory()

        # Current state
        self.state = AgentState.AT_HOME
        self.current_mode: str | None = None
        self.current_route: list[str] | None = None
        self.route_index = 0
        self.departure_time = 0.0
        self.commute_start_time = 0.0

        # Track if we've claimed a car from the household this trip
        self._holding_car = False

        # Phase 2: Track denied metro boarding count (SUB-03, task 3.2)
        self._denied_boarding_count = 0

        # Shopping extension — pending shopping needs for the ShopChoiceModel
        self.shopping_needs: list[dict] = []
        self._shopped_today = False

    @property
    def morning_departure_time(self) -> float:
        return self.schedule.leave_home_min + self.departure_adjustment

    @property
    def evening_departure_time(self) -> float:
        return self.schedule.return_home_min()

    def available_modes(self) -> list[str]:
        """Return list of transport modes this agent can currently use."""
        modes: list[str] = ["walk", "bus", "auto"]

        if self.has_bike:
            modes.append("bike")

        if self.has_car:
            # Household car-sharing: check if a car is actually available
            if self.household is not None:
                if self.household.cars_available > 0:
                    modes.append("car")
            else:
                modes.append("car")

        if not self.model.network.disabled_metro_lines:
            modes.append("metro")

        # Public shared modes — available to everyone (distance-gated in choose_mode)
        modes.append("bike_share")
        modes.append("e_rickshaw")

        return modes

    def step(self) -> None:
        """Executed at every tick (5 minutes) by the scheduler."""
        current_time = self.model.sim_time_minutes % (24 * 60)

        # 1. Check for departure from home (Morning commute)
        if self.state == AgentState.AT_HOME:
            if current_time >= self.morning_departure_time:
                self._current_leg_index = 0
                self._depart_next_leg()

        # 2. Check for departure from work/activity (multi-leg or evening)
        elif self.state == AgentState.AT_WORK:
            # Try discretionary shopping during evening window
            if not self._shopped_today and current_time >= 17 * 60:
                self._maybe_shop(current_time)
            if current_time >= self.evening_departure_time:
                self.decide_and_depart(is_morning=False)

        # 3. Advance routing if actively commuting
        elif self.state == AgentState.COMMUTING:
            self.advance_commute()

    def _depart_next_leg(self) -> None:
        """Depart on the next leg of the multi-leg schedule."""
        legs = self.schedule.get_legs()
        if not legs or self._current_leg_index >= len(legs):
            # All legs completed or no legs — go home
            self.state = AgentState.AT_HOME
            return

        origin_act, dest_act = legs[self._current_leg_index]
        source = origin_act.location_node
        target = dest_act.location_node

        if not target or source == target:
            self._current_leg_index += 1
            if dest_act.activity_type == ActivityType.HOME:
                self.state = AgentState.AT_HOME
            else:
                self.state = AgentState.AT_WORK
            return

        self._start_commute(source, target, dest_act)

    def _start_commute(
        self, source: str, target: str, dest_activity: Activity | None = None
    ) -> None:
        """Choose mode, find route, and start commuting from source to target."""
        chosen_mode = self.choose_mode(source, target)
        self.current_mode = chosen_mode

        # If choosing car, request from household
        if chosen_mode == "car" and self.household is not None:
            if not self.household.request_car():
                # Car not available — fallback to bus
                chosen_mode = "bus"
                self.current_mode = "bus"
            else:
                self._holding_car = True

        # Phase 2: Metro boarding capacity check (SUB-03, task 3.2)
        if chosen_mode == "metro":
            # Find which metro line the agent is near
            metro_line = self._detect_metro_line(source)
            if metro_line:
                boarded, wait_min = self.model.network.try_board_metro(
                    metro_line, self.model.sim_time_minutes
                )
                if not boarded:
                    self._denied_boarding_count += 1
                    # Record a bad metro outcome in memory so frustration builds
                    # and the agent naturally avoids metro on subsequent ticks/days.
                    self.memory.record(CommuteOutcome(
                        mode="metro",
                        travel_time_min=60.0,  # penalty: treated as a very slow trip
                        monetary_cost=0.0,
                        comfort_score=0.1,     # terrible experience
                    ))
                    if self._denied_boarding_count >= 3:
                        # Denied 3x — reroute via bus, reset denial counter
                        chosen_mode = "bus"
                        self.current_mode = "bus"
                        self._denied_boarding_count = 0
                    else:
                        # Try again next tick
                        self.state = AgentState.AT_HOME
                        return

        # Find physical shortest path in multi-modal network
        net: MultiModalNetwork = self.model.network
        route = net.find_shortest_path(source, target, chosen_mode)

        if route:
            self.current_route = route
            self.route_index = 0
            self.state = AgentState.COMMUTING
            self.commute_start_time = self.model.sim_time_minutes
        else:
            # Fallback to walking
            route = net.find_shortest_path(source, target, "walk")
            if route:
                self.current_route = route
                self.route_index = 0
                self.current_mode = "walk"
                self.state = AgentState.COMMUTING
                self.commute_start_time = self.model.sim_time_minutes
            else:
                # Teleport as absolute failsafe
                self.state = AgentState.AT_WORK

    def decide_and_depart(self, is_morning: bool) -> None:
        """Choose mode and route, and transition to commuting state."""
        source = self.home_node if is_morning else (self.work_node or self.home_node)
        target = (self.work_node or self.home_node) if is_morning else self.home_node

        if not target or source == target:
            # Non-worker or already there
            self.state = AgentState.AT_WORK if is_morning else AgentState.AT_HOME
            return

        self._start_commute(source, target)

    def choose_mode(self, source: str, target: str) -> str:
        """Discrete-choice MNL mode selection using the ModeChoiceModel."""
        net: MultiModalNetwork = self.model.network
        rain = net.weather_rain_intensity

        # Approximate travel distance between nodes (km)
        lat_diff = net.g.nodes[target]["lat"] - net.g.nodes[source]["lat"]
        lon_diff = net.g.nodes[target]["lon"] - net.g.nodes[source]["lon"]
        distance_km = math.sqrt(lat_diff**2 + lon_diff**2) * 111.0

        # Build mode alternatives
        available = self.available_modes()
        alts: list[ModeAlternative] = []

        for mode in available:
            if mode not in _MODE_PROFILE:
                continue

            mins_per_km, rs_per_km, comfort = _MODE_PROFILE[mode]

            # Walk is only realistic for short trips
            if mode == "walk" and distance_km > 3.0:
                continue

            # Bike-share only for trips ≤5 km (docking station coverage)
            if mode == "bike_share" and distance_km > 5.0:
                continue

            # E-rickshaw only for trips ≤8 km (first/last mile connector)
            if mode == "e_rickshaw" and distance_km > 8.0:
                continue

            # Get weather penalty from rain exposure
            weather_penalty = _RAIN_EXPOSURE.get(mode, 0.0) * rain

            # Use real network routing for travel time if possible
            path = net.find_shortest_path(source, target, mode)
            if path:
                travel_time_min = net.calculate_path_travel_time(path, mode)
            else:
                travel_time_min = mins_per_km * distance_km

            monetary_cost = self.calculate_monetary_cost(mode, distance_km) / 100.0

            # Adjust comfort for congestion/crowding
            comfort = self._adjust_comfort(mode, comfort, rain)

            alts.append(
                ModeAlternative(
                    mode=mode,
                    travel_time_min=travel_time_min,
                    monetary_cost=monetary_cost,
                    comfort_score=comfort,
                    weather_penalty=weather_penalty,
                )
            )

        if not alts:
            return "walk"

        # Use the model's shared ModeChoiceModel
        return self.model.mode_choice_model.choose(self, alts)

    def _adjust_comfort(self, mode: str, base_comfort: float, rain: float) -> float:
        """Adjust comfort based on dynamic conditions (congestion, crowding, rain)."""
        if mode == "metro":
            return max(
                0.2, base_comfort - 0.4 * (self.model.metrics.metro_load_pct / 100.0)
            )
        elif mode == "bus":
            return max(
                0.1, base_comfort - 0.4 * self.model.metrics.road_congestion_index
            )
        elif mode in ("walk", "bike"):
            return max(0.0, base_comfort - 1.0 * rain)
        elif mode == "auto":
            return max(0.2, base_comfort - 0.3 * rain)
        return base_comfort

    def calculate_monetary_cost(self, mode: str, dist_km: float) -> int:
        """Get standard fare costs in Paise."""
        # Metro: ₹40 flat or ₹0 if they have a pre-purchased pass
        if mode == "metro":
            return 0 if self.has_metro_pass else 4000

        # Bus: ₹20 flat, scales with bus capacity multiplier policy (cheaper bus incentives)
        elif mode == "bus":
            base_fare = 2000
            # Bus fare could be subsidized if bus capacity is boosted
            if self.model.network.bus_capacity_multiplier > 1.0:
                return int(
                    base_fare * (2.0 - self.model.network.bus_capacity_multiplier)
                )
            return base_fare

        # Car: ₹12/km base + fuel price delta policy in Paise
        elif mode == "car":
            fuel_cost_per_km = 1200 + self.model.network.fuel_price_delta_paise
            return int(fuel_cost_per_km * dist_km)

        # Auto: ₹15 base + ₹15/km + 50% of fuel price delta (autos also burn fuel)
        elif mode == "auto":
            fuel_delta = self.model.network.fuel_price_delta_paise
            auto_cost_per_km = 1500 + int(0.5 * fuel_delta)
            return int(1500 + auto_cost_per_km * dist_km)

        # Bike: ₹1.5/km maintenance
        elif mode == "bike":
            return int(150 * dist_km)

        # Bike-share: ₹10 flat + ₹1/km
        elif mode == "bike_share":
            return int(1000 + 100 * dist_km)

        # E-rickshaw: ₹20 base + ₹8/km
        elif mode == "e_rickshaw":
            return int(2000 + 800 * dist_km)

        return 0  # Walk is free

    def advance_commute(self) -> None:
        """Physical stepping along the path route."""
        if not self.current_route:
            self.state = AgentState.AT_WORK
            return

        net: MultiModalNetwork = self.model.network

        ticks_passed = self.model.sim_time_minutes - self.commute_start_time
        estimated_total_time = net.calculate_path_travel_time(
            self.current_route, self.current_mode
        )

        if ticks_passed >= estimated_total_time:
            # Commute finished!
            duration = ticks_passed
            rain = net.weather_rain_intensity
            comfort = self._adjust_comfort(
                self.current_mode,
                _MODE_PROFILE.get(self.current_mode, (0, 0, 0.3))[2],
                rain,
            )

            # Calculate monetary cost for this trip
            lat_diff = (
                net.g.nodes[self.current_route[-1]]["lat"]
                - net.g.nodes[self.current_route[0]]["lat"]
            )
            lon_diff = (
                net.g.nodes[self.current_route[-1]]["lon"]
                - net.g.nodes[self.current_route[0]]["lon"]
            )
            dist_km = math.sqrt(lat_diff**2 + lon_diff**2) * 111.0
            cost = self.calculate_monetary_cost(self.current_mode, dist_km) / 100.0

            # Record structured outcome in memory
            outcome = CommuteOutcome(
                mode=self.current_mode,
                travel_time_min=duration,
                monetary_cost=cost,
                comfort_score=comfort,
            )
            self.memory.record(outcome)

            # Release car back to household if we were holding one
            if self._holding_car and self.household is not None:
                self.household.release_car()
                self._holding_car = False

            # Adapt schedule if commute was terrible (>50 mins)
            if duration > 50.0:
                # Leave 15 mins earlier tomorrow to beat congestion
                self.departure_adjustment = max(
                    -120.0, self.departure_adjustment - 15.0
                )
            elif duration < 25.0 and self.departure_adjustment < 0.0:
                # Gradually return to normal schedule if traffic improves
                self.departure_adjustment += 5.0

            # State transition
            if self.state == AgentState.COMMUTING:
                if self.work_node and self.current_route[-1] == self.work_node:
                    self.state = AgentState.AT_WORK
                elif self.current_route[-1] == self.home_node:
                    self.state = AgentState.AT_HOME
                else:
                    # Intermediate leg (e.g. school escort) — proceed to next leg
                    self._current_leg_index += 1
                    legs = self.schedule.get_legs()
                    if self._current_leg_index < len(legs):
                        self.state = AgentState.AT_WORK  # temporary "at activity"
                        self._depart_next_leg()
                    else:
                        self.state = AgentState.AT_WORK

            self.current_route = None
            self.route_index = 0
        else:
            # Advance route index proportionally
            fraction = ticks_passed / max(1.0, estimated_total_time)
            self.route_index = min(
                len(self.current_route) - 1, int(fraction * len(self.current_route))
            )

    def adapt_behavior(self) -> None:
        """Called daily to adapt schedule departure times based on commute performance.

        If the last three commutes on their active mode were 15% slower than their
        rolling average for that mode, they shift departure time 15 minutes earlier.
        """
        if self.current_mode:
            buf = self.memory.by_mode.get(self.current_mode)
            if buf and len(buf) >= 3:
                last_three = list(buf)[-3:]
                avg = sum(o.travel_time_min for o in buf) / len(buf)
                if all(o.travel_time_min > avg * 1.15 for o in last_three):
                    # Shift leave time earlier by 15 mins (up to a limit of 06:00 AM)
                    if self.schedule.activities and len(self.schedule.activities) > 1:
                        second_act = self.schedule.activities[1]
                        old_start = second_act.start_time_min
                        new_start = max(6 * 60, old_start - 15)
                        second_act.start_time_min = new_start
                        self.schedule.leave_home_min = new_start
                    else:
                        self.schedule.leave_home_min = max(
                            6 * 60, self.schedule.leave_home_min - 15
                        )

    def reset_for_new_day(self) -> None:
        """Reset agent state for a new simulation day.

        Called at the 24h boundary. Puts the agent back home, releases
        any held car, and resets the activity leg index. Memory is
        preserved so agents remember yesterday's frustrations.
        """
        self.state = AgentState.AT_HOME
        self.current_mode = None
        self.current_route = None
        self.route_index = 0
        self._current_leg_index = 0
        self._shopped_today = False
        self._denied_boarding_count = 0  # Phase 2: reset denied boardings

        # Release car back to household if we were holding one
        if self._holding_car and self.household is not None:
            self.household.release_car()
            self._holding_car = False

    def _detect_metro_line(self, node_id: str) -> str | None:
        """Detect which metro line is accessible from the given node.

        Checks neighboring nodes for metro stations and returns the line name.
        Returns None if no metro station is nearby.
        """
        net = self.model.network
        # Check if the node itself has a metro station attribute
        node_data = net.g.nodes.get(node_id, {})
        if node_data.get("type") == "metro_station":
            return node_data.get("line", "yellow")

        # Check adjacent nodes for metro stations
        for neighbor in net.g.neighbors(node_id):
            nbr_data = net.g.nodes.get(neighbor, {})
            if nbr_data.get("type") == "metro_station":
                return nbr_data.get("line", "yellow")

        # Check if node has metro_station flag (synthetic grid)
        if node_data.get("metro_station"):
            # Try to find line from nearby metro station nodes
            for neighbor in net.g.neighbors(node_id):
                nbr_data = net.g.nodes.get(neighbor, {})
                if nbr_data.get("type") == "metro_station":
                    return nbr_data.get("line", "yellow")
            return "yellow"  # default fallback

        return None

    # -----------------------------------------------------------------------
    # Shopping — discretionary evening shop choice (ShopChoiceModel wiring)
    # -----------------------------------------------------------------------

    def _maybe_shop(self, current_time: int) -> None:
        """Evaluate whether to make a discretionary shopping trip.

        Triggered during the evening window (after 17:00) with a 10% per-tick
        probability. Uses the ShopChoiceModel to pick a destination from
        nearby stalls and stores.
        """
        rng = self.model._np_rng

        # 10% per-tick chance of generating a shopping need
        if rng.random() > 0.10:
            return

        # Check that model has shop infrastructure
        if not hasattr(self.model, "stalls") or not hasattr(self.model, "stores"):
            return

        # Generate a shopping need based on occupation/income
        product_types = ["food", "clothes", "accessories"]
        weights = [0.6, 0.25, 0.15]
        product_type = product_types[int(rng.choice(len(product_types), p=weights))]

        # Build alternatives from nearby stalls and stores
        alternatives = self._build_shop_alternatives(product_type)
        if not alternatives:
            return

        # Use the model's ShopChoiceModel to choose
        if (
            not hasattr(self.model, "shop_choice_model")
            or self.model.shop_choice_model is None
        ):
            return

        # Build a lightweight agent-like object for the ShopChoiceModel
        from simulation.economic_agents import _AgentProxy

        proxy = _AgentProxy(
            income_bracket=self.income_bracket,
            schedule=self.schedule,
        )

        rain = self.model.network.weather_rain_intensity
        chosen = self.model.shop_choice_model.choose(
            proxy, alternatives, rain_intensity=rain
        )

        # Process the purchase
        self._shopped_today = True

        if chosen.shop_type == "delivery":
            # Delivery — no physical travel, dispatch delivery agent
            if hasattr(self.model, "delivery_agents") and self.model.delivery_agents:
                delivery = list(self.model.delivery_agents.values())[0]
                fee = delivery.get_delivery_fee(30.0, rain)
                # Agent gets charged but doesn't move
                self.shopping_needs.append(
                    {
                        "product": product_type,
                        "shop_id": chosen.shop_id,
                        "type": "delivery",
                        "cost": fee,
                        "tick": self.model.current_tick,
                    }
                )
        else:
            # Physical shopping — record as a transaction
            self.shopping_needs.append(
                {
                    "product": product_type,
                    "shop_id": chosen.shop_id,
                    "type": chosen.shop_type,
                    "cost": chosen.price_level * 100.0,
                    "tick": self.model.current_tick,
                }
            )

            # If the shop is a stall, reduce its inventory
            if chosen.shop_id in getattr(self.model, "stalls", {}):
                stall = self.model.stalls[chosen.shop_id]
                stall.inventory = max(0.0, stall.inventory - 0.05)

    def _build_shop_alternatives(self, product_type: str) -> list:
        """Build ShopAlternative list from nearby stalls and stores."""
        from simulation.economic_agents import ShopAlternative

        net = self.model.network
        alternatives = []

        # Current agent location
        if self.current_route and self.route_index < len(self.current_route):
            agent_node = self.current_route[self.route_index]
        elif self.work_node:
            agent_node = self.work_node
        else:
            agent_node = self.home_node

        agent_data = net.g.nodes.get(agent_node, {})
        agent_lat = agent_data.get("lat", 0.0)
        agent_lon = agent_data.get("lon", 0.0)

        # Scan stalls
        for stall_id, stall in getattr(self.model, "stalls", {}).items():
            if stall.is_disrupted_today or stall.inventory <= 0:
                continue
            # Check product match
            match = 0.0
            if product_type == "food" and stall.stall_type == "food":
                match = 0.9
            elif product_type == "clothes" and stall.stall_type == "clothes":
                match = 0.9
            elif product_type == "accessories" and stall.stall_type == "accessories":
                match = 0.9
            else:
                match = 0.2  # partial match

            stall_data = net.g.nodes.get(str(stall.current_location), {})
            stall_lat = stall_data.get("lat", 0.0)
            stall_lon = stall_data.get("lon", 0.0)
            dist_km = (
                math.sqrt((agent_lat - stall_lat) ** 2 + (agent_lon - stall_lon) ** 2)
                * 111.0
            )

            if dist_km > 5.0:
                continue

            stall_type_map = {
                "food": "food_stall",
                "clothes": "clothes_stall",
                "accessories": "accessories_stall",
            }

            alternatives.append(
                ShopAlternative(
                    shop_id=stall_id,
                    shop_type=stall_type_map.get(stall.stall_type, "food_stall"),
                    distance_km=round(dist_km, 2),
                    travel_time_min=round(dist_km * 5.0, 1),  # rough estimate
                    price_level=0.3,  # stalls are cheap
                    product_match=match,
                )
            )

        # Scan stores
        for store_id, store in getattr(self.model, "stores", {}).items():
            if store.inventory <= 0:
                continue
            store_data = net.g.nodes.get(str(store.store_node), {})
            store_lat = store_data.get("lat", 0.0)
            store_lon = store_data.get("lon", 0.0)
            dist_km = (
                math.sqrt((agent_lat - store_lat) ** 2 + (agent_lon - store_lon) ** 2)
                * 111.0
            )

            if dist_km > 5.0:
                continue

            alternatives.append(
                ShopAlternative(
                    shop_id=store_id,
                    shop_type="formal_store",
                    distance_km=round(dist_km, 2),
                    travel_time_min=round(dist_km * 3.5, 1),
                    price_level=0.7,  # formal stores are pricier
                    product_match=0.8,  # stores carry everything
                )
            )

        # Always add delivery option
        alternatives.append(
            ShopAlternative(
                shop_id=-1,
                shop_type="delivery",
                distance_km=0.0,
                travel_time_min=30.0,
                price_level=0.5,
                product_match=0.7,
            )
        )

        return alternatives
