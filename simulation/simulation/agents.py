"""Citizen Agent representation and behavior.

Defines the Agent properties, decision functions (utility model),
schedules, memory, and state transitions.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING
import mesa

if TYPE_CHECKING:
    from simulation.engine import UrbanModel
    from simulation.network import MultiModalNetwork


class AgentState:
    AT_HOME = "AT_HOME"
    DEPARTING = "DEPARTING"
    COMMUTING = "COMMUTING"
    AT_WORK = "AT_WORK"
    RETURNING = "RETURNING"


class CitizenAgent(mesa.Agent):
    """An individual citizen agent commuting in the city."""

    def __init__(
        self,
        unique_id: int,
        model: UrbanModel,
        home_node: str,
        work_node: str,
        income_bracket: int,  # 1 to 5
        age: int,
        has_car: bool,
        has_bike: bool,
        has_metro_pass: bool,
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

        # Scheduling (in simulated minutes from midnight)
        # Average morning departure: 8:00 AM (480 mins) to 9:30 AM (570 mins)
        self.base_morning_departure = 480 + random.randint(0, 90)
        # Average workday duration: 8 hours (480 mins)
        self.work_duration = 480 + random.randint(-30, 90)

        # Adaptation adjustments (learned through experience)
        self.departure_adjustment = 0.0

        # Memory buffer (stores outcomes of last 10 commutes)
        # outcome format: {"mode": str, "duration": float, "comfort": float}
        self.memory: list[dict] = []

        # Current state
        self.state = AgentState.AT_HOME
        self.current_mode: str | None = None
        self.current_route: list[str] | None = None
        self.route_index = 0
        self.departure_time = 0.0
        self.commute_start_time = 0.0

    @property
    def morning_departure_time(self) -> float:
        return self.base_morning_departure + self.departure_adjustment

    @property
    def evening_departure_time(self) -> float:
        return self.morning_departure_time + self.work_duration

    def step(self) -> None:
        """Executed at every tick (5 minutes) by the scheduler."""
        current_time = self.model.sim_time_minutes % (24 * 60)

        # 1. Check for departure from home (Morning commute)
        if self.state == AgentState.AT_HOME:
            if current_time >= self.morning_departure_time:
                self.decide_and_depart(is_morning=True)

        # 2. Check for departure from work (Evening commute)
        elif self.state == AgentState.AT_WORK:
            if current_time >= self.evening_departure_time:
                self.decide_and_depart(is_morning=False)

        # 3. Advance routing if actively commuting
        elif self.state == AgentState.COMMUTING:
            self.advance_commute()

    def decide_and_depart(self, is_morning: bool) -> None:
        """Choose mode and route, and transition to commuting state."""
        source = self.home_node if is_morning else self.work_node
        target = self.work_node if is_morning else self.home_node

        if not target or source == target:
            # Non-worker or already there
            self.state = AgentState.AT_WORK if is_morning else AgentState.AT_HOME
            return

        # Choose transport mode based on utility model
        chosen_mode = self.choose_mode(source, target)
        self.current_mode = chosen_mode

        # Find physical shortest path in multi-modal network
        net: MultiModalNetwork = self.model.network
        route = net.find_shortest_path(source, target, chosen_mode)

        if route:
            self.current_route = route
            self.route_index = 0
            self.state = AgentState.COMMUTING
            self.commute_start_time = self.model.sim_time_minutes
        else:
            # Fallback if no route found (e.g. metro shutdown and no road connection)
            # Default to walking
            route = net.find_shortest_path(source, target, "walk")
            if route:
                self.current_route = route
                self.route_index = 0
                self.current_mode = "walk"
                self.state = AgentState.COMMUTING
                self.commute_start_time = self.model.sim_time_minutes
            else:
                # Teleport as absolute failsafe
                self.state = AgentState.AT_WORK if is_morning else AgentState.AT_HOME

    def choose_mode(self, source: str, target: str) -> str:
        """Discrete-choice Multinomial Logit Utility Model."""
        available_modes = ["walk", "bus"]
        if self.has_bike:
            available_modes.append("bike")
        if self.has_car:
            available_modes.append("car")
        if not self.model.network.disabled_metro_lines:
            available_modes.append("metro")
        available_modes.append("auto")

        net: MultiModalNetwork = self.model.network
        utilities = {}

        # Coefficient Weights depending on Income bracket (1-5, low to high)
        # Low income has high cost sensitivity, high income has high time sensitivity
        beta_time = -0.05 - 0.03 * self.income_bracket
        beta_cost = (
            -0.15 + 0.025 * self.income_bracket
        )  # less negative as income increases
        beta_comfort = 0.5 + 0.1 * self.income_bracket

        # Weather multiplier
        rain = net.weather_rain_intensity

        # Approximate travel distance between nodes (km)
        lat_diff = net.g.nodes[target]["lat"] - net.g.nodes[source]["lat"]
        lon_diff = net.g.nodes[target]["lon"] - net.g.nodes[source]["lon"]
        distance_km = math.sqrt(lat_diff**2 + lon_diff**2) * 111.0

        for mode in available_modes:
            # 1. Retrieve travel time (estimate based on current congestion)
            path = net.find_shortest_path(source, target, mode)
            if not path:
                utilities[mode] = -999.0
                continue
            travel_time_min = net.calculate_path_travel_time(path, mode)

            # 2. Retrieve monetary cost in Paise
            monetary_cost_paise = self.calculate_monetary_cost(mode, distance_km)

            # Convert cost to Rupees for utility scaling (since beta is calibrated)
            cost_rs = monetary_cost_paise / 100.0

            # 3. Retrieve base comfort
            comfort = self.get_comfort_score(mode, rain)

            # 4. Habit bonus
            habit_bonus = self.get_habit_bonus(mode)

            # 5. Weather penalty (applied heavily on open modes: walking, biking, auto)
            weather_penalty = 0.0
            if rain > 0:
                if mode in ("walk", "bike"):
                    weather_penalty = -3.5 * rain
                elif mode == "auto":
                    weather_penalty = -1.0 * rain

            # Utility score
            u = (
                beta_time * travel_time_min
                + beta_cost * cost_rs
                + beta_comfort * comfort
                + weather_penalty
                + habit_bonus
            )
            utilities[mode] = u

        # Softmax sampling to pick mode
        # Extract exponents
        try:
            max_u = max(utilities.values())
            exps = {m: math.exp(u - max_u) for m, u in utilities.items()}
            sum_exps = sum(exps.values())
            probs = {m: val / sum_exps for m, val in exps.items()}
        except Exception:
            # Fallback to equal probs if overflow
            probs = {m: 1.0 / len(utilities) for m in utilities}

        # Weighted selection
        r = random.random()
        cumulative = 0.0
        for mode, prob in probs.items():
            cumulative += prob
            if r <= cumulative:
                return mode

        return "walk"

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

        # Auto: ₹15 base + ₹15/km
        elif mode == "auto":
            return int(1500 + 1500 * dist_km)

        # Bike: ₹1.5/km maintenance
        elif mode == "bike":
            return int(150 * dist_km)

        return 0  # Walk is free

    def get_comfort_score(self, mode: str, rain: float) -> float:
        """Retrieve comfort score for travel mode."""
        if mode == "car":
            return 1.0
        elif mode == "bike":
            return 0.5 - 1.0 * rain
        elif mode == "auto":
            return 0.7 - 0.3 * rain
        elif mode == "metro":
            # Decreases if metro is overcrowded (represented globally in model)
            return max(0.2, 0.8 - 0.4 * (self.model.metrics.metro_load_pct / 100.0))
        elif mode == "bus":
            return max(0.1, 0.6 - 0.4 * (self.model.metrics.road_congestion_index))
        elif mode == "walk":
            return 0.3 - 1.3 * rain
        return 0.3

    def get_habit_bonus(self, mode: str) -> float:
        """Add positive reward for modes that have been successful in memory."""
        if not self.memory:
            return 0.0

        matches = [m for m in self.memory if m["mode"] == mode]
        if not matches:
            return 0.0

        # Average duration of recent commutes in this mode
        avg_dur = sum(m["duration"] for m in matches) / len(matches)

        # If average duration was fast (< 30 mins) and highly comfortable, give habit bonus
        avg_comfort = sum(m["comfort"] for m in matches) / len(matches)

        bonus = 0.0
        if avg_dur < 40.0:
            bonus += 0.5
        if avg_comfort > 0.6:
            bonus += 0.5
        return bonus

    def advance_commute(self) -> None:
        """Physical stepping along the path route."""
        if not self.current_route:
            self.state = AgentState.AT_WORK
            return

        # An agent travels N grid links per 5-minute tick depending on speed/congestion
        # Walking/biking takes longer. Car/Bus/Metro are faster.
        # Let's say: each tick, they advance a distance corresponding to 5 mins of travel
        # For simplicity, let's advance their position on the route path index.
        # We can calculate travel times per link and advance appropriately.
        net: MultiModalNetwork = self.model.network

        ticks_passed = self.model.sim_time_minutes - self.commute_start_time
        estimated_total_time = net.calculate_path_travel_time(
            self.current_route, self.current_mode
        )

        if ticks_passed >= estimated_total_time:
            # Commute finished!
            duration = ticks_passed
            comfort = self.get_comfort_score(
                self.current_mode, net.weather_rain_intensity
            )

            # Record outcome in memory
            self.memory.append(
                {"mode": self.current_mode, "duration": duration, "comfort": comfort}
            )
            if len(self.memory) > 10:
                self.memory.pop(0)

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
                if self.current_route[-1] == self.work_node:
                    self.state = AgentState.AT_WORK
                else:
                    self.state = AgentState.AT_HOME

            self.current_route = None
            self.route_index = 0
        else:
            # Advance route index proportionally
            fraction = ticks_passed / max(1.0, estimated_total_time)
            self.route_index = min(
                len(self.current_route) - 1, int(fraction * len(self.current_route))
            )
