"""Heavy freight driver dataclasses and state machine.

Provides ``FreightDriver``, ``FreightOrder``, and ``FreightState`` — the core
data model for simulating urban goods movement (trucks / tempos).  These are
pure-Python dataclasses designed to be wrapped in a Mesa agent for the
simulation engine (similar to how ``DeliveryAgent`` was ported into
``simulation/simulation/economic_agents.py``).

Delhi-specific constraints:
- Trucks are banned from inner-city roads during 7–11 AM (configurable).
- Fare scales with both distance and cargo weight.
- Fuel cost is 100% passed through (freight is extremely fuel-sensitive).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

NodeID = int


class FreightState(str, Enum):
    """State machine states for a freight driver."""

    IDLE = "idle"
    EN_ROUTE_PICKUP = "en_route_pickup"
    LOADING = "loading"
    EN_ROUTE_DELIVERY = "en_route_delivery"
    UNLOADING = "unloading"
    RETURNING = "returning"


@dataclass
class FreightOrder:
    """A single freight delivery order.

    Attributes:
        order_id: Unique identifier.
        pickup_node: Network node where goods are picked up.
        delivery_node: Network node where goods are delivered.
        weight_tonnes: Cargo weight in metric tonnes (1–20 for urban freight).
        deadline_min: Delivery deadline in simulation-minutes from start of day.
        priority: 1 = normal, 2 = urgent, 3 = perishable (perishable pays more).
    """

    order_id: int
    pickup_node: NodeID
    delivery_node: NodeID
    weight_tonnes: float
    deadline_min: int = 24 * 60  # default: end of day
    priority: int = 1


@dataclass
class FreightDriver:
    """Heavy freight driver (truck / tempo) for urban goods movement.

    Pure-Python dataclass with state-machine logic.  Wrap in a Mesa agent for
    tick-based simulation.

    Attributes:
        id: Unique driver identifier.
        depot_node: Home depot / parking location.
        current_location: Current network node.
        vehicle_capacity_tonnes: Maximum cargo the vehicle can carry.
        current_load_tonnes: Current cargo weight.
        state: Current state in the freight lifecycle.
        current_order: The freight order currently being fulfilled (or None).
        completed_orders: Running count of deliveries completed.
        total_distance_km: Cumulative distance driven.
        earnings: Cumulative earnings in ₹.
        fuel_cost_accumulated: Cumulative fuel expenditure in ₹.
        restricted_hours: (start, end) hours when trucks are banned from
            inner-city roads.  Default: 7–11 AM (Delhi regulation).
    """

    id: int
    depot_node: NodeID
    current_location: NodeID
    vehicle_capacity_tonnes: float = 10.0
    current_load_tonnes: float = 0.0
    state: FreightState = FreightState.IDLE
    current_order: FreightOrder | None = None
    completed_orders: int = 0
    total_distance_km: float = 0.0
    earnings: float = 0.0
    fuel_cost_accumulated: float = 0.0
    restricted_hours: tuple[int, int] = (7, 11)

    # -- Query helpers -------------------------------------------------------

    def can_operate(self, current_hour: int) -> bool:
        """Return True if the truck is allowed to operate at *current_hour*.

        Delhi bans heavy vehicles from inner-city roads during
        ``restricted_hours`` (default 7–11 AM).
        """
        start, end = self.restricted_hours
        return not (start <= current_hour < end)

    @property
    def available_capacity(self) -> float:
        """Remaining cargo capacity in tonnes."""
        return max(0.0, self.vehicle_capacity_tonnes - self.current_load_tonnes)

    # -- Order management ----------------------------------------------------

    def assign_order(self, order: FreightOrder) -> None:
        """Assign a freight order and transition to EN_ROUTE_PICKUP.

        Raises:
            ValueError: If the order's weight exceeds available capacity.
            RuntimeError: If the driver is not IDLE.
        """
        if self.state != FreightState.IDLE:
            raise RuntimeError(
                f"Cannot assign order: driver {self.id} is in state {self.state.value}"
            )
        if order.weight_tonnes > self.available_capacity:
            raise ValueError(
                f"Order weight {order.weight_tonnes}t exceeds available capacity "
                f"{self.available_capacity}t for driver {self.id}"
            )
        self.current_order = order
        self.state = FreightState.EN_ROUTE_PICKUP

    # -- State-machine step --------------------------------------------------

    def step(self, current_hour: int, travel_time_min: float = 0.0) -> FreightState:
        """Advance the driver's state machine by one tick.

        The caller is responsible for providing ``travel_time_min`` (from the
        routing engine) and moving the driver's ``current_location`` on the
        network graph.  This method handles state transitions only.

        Args:
            current_hour: Current hour (0–23) for restricted-hours check.
            travel_time_min: Travel time consumed this tick (used to decide
                when LOADING / UNLOADING finishes — simplified to 1-tick
                transitions here; a Mesa wrapper can add duration logic).

        Returns:
            The driver's new state after the transition.
        """
        # If truck is restricted right now, stay put (don't transition)
        if not self.can_operate(current_hour) and self.state in (
            FreightState.EN_ROUTE_PICKUP,
            FreightState.EN_ROUTE_DELIVERY,
            FreightState.RETURNING,
        ):
            return self.state

        if self.state == FreightState.EN_ROUTE_PICKUP:
            # Arrived at pickup? → start loading
            if self.current_order and self.current_location == self.current_order.pickup_node:
                self.state = FreightState.LOADING
                self.current_load_tonnes = self.current_order.weight_tonnes

        elif self.state == FreightState.LOADING:
            # Loading takes 1 tick (simplified), then depart
            self.state = FreightState.EN_ROUTE_DELIVERY

        elif self.state == FreightState.EN_ROUTE_DELIVERY:
            # Arrived at delivery? → start unloading
            if self.current_order and self.current_location == self.current_order.delivery_node:
                self.state = FreightState.UNLOADING

        elif self.state == FreightState.UNLOADING:
            # Unloading takes 1 tick, then mark complete and return
            self.current_load_tonnes = 0.0
            self.completed_orders += 1
            self.current_order = None
            self.state = FreightState.RETURNING

        elif self.state == FreightState.RETURNING:
            # Arrived back at depot? → idle
            if self.current_location == self.depot_node:
                self.state = FreightState.IDLE

        return self.state

    # -- Fare calculation ----------------------------------------------------

    @staticmethod
    def calculate_freight_fare(
        distance_km: float,
        weight_tonnes: float,
        fuel_price_delta_paise: int = 0,
    ) -> float:
        """Compute freight fare in ₹.

        Formula:
            fare = base_per_km × distance × weight_factor + fuel_surcharge

        - base_per_km: ₹18/km for urban freight
        - weight_factor: 1.0 for ≤5t, scales linearly to 2.0 at 20t
        - fuel_surcharge: 100% pass-through of fuel price delta (freight is
          extremely fuel-sensitive)

        Args:
            distance_km: Trip distance.
            weight_tonnes: Cargo weight.
            fuel_price_delta_paise: Policy fuel price change in paise.

        Returns:
            Fare in ₹.
        """
        base_per_km = 18.0  # ₹18/km base
        # Weight factor: 1.0 at ≤5t, linear to 2.0 at 20t
        weight_factor = 1.0 + max(0.0, weight_tonnes - 5.0) / 15.0
        base_fare = base_per_km * distance_km * weight_factor

        # 100% fuel pass-through (convert paise to ₹)
        fuel_surcharge = (fuel_price_delta_paise / 100.0) * distance_km

        return base_fare + fuel_surcharge
