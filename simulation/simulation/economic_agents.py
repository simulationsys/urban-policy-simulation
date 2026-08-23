"""Mesa-compatible wrappers for AI subsystem economic agents.

Ports StallOwner, StoreManager, StoreStaff, DeliveryAgent, and
WholesaleSupplier from ai/sim/agents/ into the Mesa simulation tick loop
with proper step() methods and dynamic restocking via the routing engine.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import mesa
import numpy as np

if TYPE_CHECKING:
    from simulation.engine import UrbanModel


# ---------------------------------------------------------------------------
# Lightweight proxy for ShopChoiceModel (avoids circular import)
# ---------------------------------------------------------------------------


@dataclass
class _AgentProxy:
    """Minimal stand-in for ai.Agent — only fields ShopChoiceModel.utility() reads."""

    income_bracket: int = 3
    schedule: object = None

    def is_busy(self) -> bool:
        if self.schedule is None:
            return False
        activities = getattr(self.schedule, "activities", [])
        from simulation.agents import ActivityType

        non_home = [a for a in activities if a.activity_type != ActivityType.HOME]
        return len(non_home) >= 2


@dataclass
class ShopAlternative:
    """One candidate shopping destination for ShopChoiceModel.

    Mirrors ai/sim/agents/shop_choice.py::ShopAlternative but as a
    plain dataclass to avoid importing the ai/ package.
    """

    shop_id: int
    shop_type: str  # "formal_store", "food_stall", "clothes_stall", "accessories_stall", "delivery"
    distance_km: float
    travel_time_min: float
    price_level: float  # 0..1
    product_match: float  # 0..1


# ---------------------------------------------------------------------------
# ShopChoiceModel (self-contained copy to avoid ai/ import)
# ---------------------------------------------------------------------------


class ShopChoiceModel:
    """MNL-based shop destination choice.

    Simplified copy of ai/sim/agents/shop_choice.py::ShopChoiceModel
    so the simulation core can run standalone without importing the ai/ package.
    """

    def __init__(self, rng: np.random.Generator | None = None) -> None:
        self.rng = rng or np.random.default_rng()
        # Utility coefficients
        self.beta_price = -0.06
        self.beta_distance = -0.10
        self.beta_travel_time = -0.04
        self.beta_product = 0.8
        self.beta_formality = 0.3

    def utility(
        self, agent: _AgentProxy, alt: ShopAlternative, rain_intensity: float = 0.0
    ) -> float:
        cost_scale = (6 - agent.income_bracket) / 3.0
        is_formal = 1.0 if alt.shop_type == "formal_store" else 0.0
        income_bonus = agent.income_bracket / 5.0
        busy_bonus = 1.5 if (agent.is_busy() and alt.shop_type == "delivery") else 0.0

        rain_penalty = 0.0
        if rain_intensity > 0.0 and alt.shop_type != "delivery":
            is_stall = alt.shop_type in (
                "food_stall",
                "clothes_stall",
                "accessories_stall",
            )
            rain_penalty = (
                (1.5 * rain_intensity) if is_stall else (0.8 * rain_intensity)
            )

        return (
            self.beta_price * alt.price_level * cost_scale
            + self.beta_distance * alt.distance_km
            + self.beta_travel_time * alt.travel_time_min
            + self.beta_product * alt.product_match
            + self.beta_formality * is_formal * income_bonus
            + busy_bonus
            - rain_penalty
        )

    def choose(
        self,
        agent: _AgentProxy,
        alts: list[ShopAlternative],
        *,
        rain_intensity: float = 0.0,
    ) -> ShopAlternative:
        if not alts:
            raise ValueError("No shop alternatives provided")
        utilities = np.array(
            [self.utility(agent, a, rain_intensity=rain_intensity) for a in alts],
            dtype=float,
        )
        gumbel = self.rng.gumbel(size=utilities.shape)
        idx = int(np.argmax(utilities + gumbel))
        return alts[idx]


# ---------------------------------------------------------------------------
# Retail memory (self-contained copy)
# ---------------------------------------------------------------------------


@dataclass
class SalesOutcome:
    revenue: float
    customers_served: int
    foot_traffic: int
    location_node: int


@dataclass
class RetailMemory:
    window: int = 7
    sales_history: deque = field(default_factory=lambda: deque(maxlen=7))
    frustration: float = 0.0

    def record_sales(self, outcome: SalesOutcome) -> None:
        self.sales_history.append(outcome)
        if outcome.revenue > 0.0:
            self.frustration = max(0.0, self.frustration - 0.25)
        else:
            self.frustration = min(5.0, self.frustration + 1.0)

    def avg_revenue(self) -> float | None:
        if not self.sales_history:
            return None
        return sum(o.revenue for o in self.sales_history) / len(self.sales_history)

    def should_relocate(self, threshold: float = 2.0) -> bool:
        return self.frustration >= threshold

    def record_disruption(self, location_node: int) -> None:
        self.sales_history.append(
            SalesOutcome(
                revenue=0.0,
                customers_served=0,
                foot_traffic=0,
                location_node=location_node,
            )
        )
        self.frustration = min(5.0, self.frustration + 1.5)


# ---------------------------------------------------------------------------
# WholesaleSupplier
# ---------------------------------------------------------------------------


class WholesaleSupplier:
    """Wholesale market supplier for restocking."""

    def __init__(self, supplier_id: int, location_node: str) -> None:
        self.id = supplier_id
        self.location_node = location_node
        self.inventory: float = 1.0
        self.base_wholesale_price: float = 20.0

    def sell_stock(
        self, buyer_cash: float, quantity: float = 1.0
    ) -> tuple[float, float]:
        price_per_unit = self.base_wholesale_price
        max_qty = min(quantity, self.inventory)
        total_cost = max_qty * price_per_unit
        if total_cost > buyer_cash:
            max_qty = buyer_cash / price_per_unit
            total_cost = max_qty * price_per_unit
        self.inventory = max(0.0, self.inventory - max_qty)
        return total_cost, max_qty


# ---------------------------------------------------------------------------
# MesaStallOwner
# ---------------------------------------------------------------------------


class MesaStallOwner(mesa.Agent):
    """Mesa-compatible roadside stall owner agent.

    Wraps ai/StallOwner with a proper step() for the Mesa tick loop.
    Dynamic restocking uses the routing engine for travel time calculation.
    """

    def __init__(
        self,
        model: UrbanModel,
        stall_id: int,
        home_node: str,
        vending_node: str,
        stall_type: str = "food",
        inventory_decay_rate: float = 0.05,
        disruption_probability: float = 0.05,
    ) -> None:
        super().__init__(model)
        self.stall_id = stall_id
        self.home_node = home_node
        self.current_location = vending_node
        self.stall_type = stall_type
        self.inventory: float = 1.0
        self.inventory_decay_rate = inventory_decay_rate
        self.disruption_probability = disruption_probability
        self.retail_memory = RetailMemory()
        self.cash_balance: float = 1000.0
        self.is_disrupted_today: bool = False
        self.is_bankrupt: bool = False
        self._has_begun_day: bool = False

    def step(self) -> None:
        """Step the stall owner in the Mesa tick loop."""
        if self.is_bankrupt:
            return

        current_time = self.model.sim_time_minutes % (24 * 60)

        # Begin day (6:00 AM)
        if current_time < 10 and not self._has_begun_day:
            self._begin_day()
            self._has_begun_day = True

        # Reset begin_day flag at midnight
        if current_time > 23 * 60:
            self._has_begun_day = False

        if self.is_disrupted_today:
            return

        # During vending hours (6:00–18:00): decay inventory, serve customers
        if 6 * 60 <= current_time <= 18 * 60:
            self.inventory = max(0.0, self.inventory - self.inventory_decay_rate)

            # Count foot traffic: agents at same node
            foot_traffic = sum(
                1
                for a in self.model.schedule.agents
                if hasattr(a, "current_route")
                and a.current_route
                and a.route_index < len(a.current_route)
                and str(a.current_route[a.route_index]) == str(self.current_location)
            )

            # Record sales outcome
            revenue = foot_traffic * self._revenue_per_customer()
            self.cash_balance += revenue
            self.retail_memory.record_sales(
                SalesOutcome(
                    revenue=revenue,
                    customers_served=foot_traffic,
                    foot_traffic=foot_traffic,
                    location_node=(
                        int(self.current_location)
                        if str(self.current_location).isdigit()
                        else 0
                    ),
                )
            )

            # Restock if inventory low
            if self.inventory < 0.2:
                self._restock_dynamic()

            # Maybe relocate if frustrated
            if self.retail_memory.should_relocate():
                self._maybe_relocate()

    def _begin_day(self) -> None:
        rng = self.model._np_rng
        self.is_disrupted_today = bool(rng.random() < self.disruption_probability)
        if self.is_disrupted_today:
            self.retail_memory.record_disruption(
                int(self.current_location)
                if str(self.current_location).isdigit()
                else 0
            )

    def _revenue_per_customer(self, base_price: float = 50.0) -> float:
        decay_discount = 1.0 - (self.inventory_decay_rate * (1.0 - self.inventory))
        return base_price * max(0.3, decay_discount)

    def _restock_dynamic(self) -> None:
        """Restock using dynamic travel time from the routing engine."""
        if not hasattr(self.model, "supplier") or self.model.supplier is None:
            # Fallback: static restock
            self.inventory = min(1.0, self.inventory + 0.8)
            return

        supplier = self.model.supplier
        net = self.model.network
        rain = net.weather_rain_intensity

        # Dynamic travel time via routing engine
        try:
            path = net.find_shortest_path(
                str(self.current_location), str(supplier.location_node), mode="auto"
            )
            if path and len(path) >= 2:
                travel_time = net.calculate_path_travel_time(path, mode="auto")
                # Convert seconds to minutes
                travel_time_min = travel_time / 60.0
            else:
                travel_time_min = 30.0
        except Exception:
            travel_time_min = 30.0

        # Rain doubles travel time
        if rain > 0.4:
            travel_time_min *= 2.0

        # Execute purchase
        cost, qty = supplier.sell_stock(
            self.cash_balance, quantity=(1.0 - self.inventory)
        )
        self.cash_balance = max(0.0, self.cash_balance - cost)
        self.inventory = min(1.0, self.inventory + qty)

    def _maybe_relocate(self) -> None:
        """Relocate to a higher-traffic node if frustration is high."""
        net = self.model.network

        # Get metro station nodes and high-traffic intersections as candidates
        candidates = []
        for node_id, data in net.g.nodes(data=True):
            if data.get("type") in ("metro_station", "intersection"):
                if str(node_id) != str(self.current_location):
                    # Estimate foot traffic from node degree
                    traffic = net.g.degree(node_id)
                    candidates.append((str(node_id), traffic))

        if not candidates:
            return

        # Pick best by traffic
        candidates.sort(key=lambda t: -t[1])
        best_node = candidates[0][0]
        self.current_location = best_node
        self.retail_memory.frustration = max(0.0, self.retail_memory.frustration - 1.5)

    def pay_fine(self, amount: float) -> None:
        self.cash_balance = max(0.0, self.cash_balance - amount)

    def evict(self) -> None:
        """Eviction spikes frustration and forces immediate relocation."""
        self.retail_memory.frustration = min(5.0, self.retail_memory.frustration + 2.0)
        self.retail_memory.frustration = max(2.5, self.retail_memory.frustration)  # Force relocation trigger
        self._maybe_relocate()

    def reset_for_new_day(self) -> None:
        self._has_begun_day = False
        self.is_disrupted_today = False


# ---------------------------------------------------------------------------
# MesaStoreManager
# ---------------------------------------------------------------------------


class MesaStoreManager(mesa.Agent):
    """Mesa-compatible formal store manager agent."""

    def __init__(
        self,
        model: UrbanModel,
        manager_id: int,
        store_node: str,
    ) -> None:
        super().__init__(model)
        self.manager_id = manager_id
        self.store_node = store_node
        self.staff_ids: list[int] = []
        self.pricing_strategy: float = 1.2
        self.inventory: float = 1.0
        self.retail_memory = RetailMemory()
        self.cash_balance: float = 5000.0
        self._last_restock_day: int = -1

    def step(self) -> None:
        current_day = self.model.sim_time_minutes // (24 * 60)

        # Weekly restocking (every 7 days)
        if current_day > self._last_restock_day and current_day % 7 == 0:
            self._restock_dynamic()
            self._last_restock_day = current_day

            # Adjust pricing based on sales trends
            self._adjust_pricing()

    def _restock_dynamic(self) -> None:
        if not hasattr(self.model, "supplier") or self.model.supplier is None:
            self.inventory = 1.0
            return

        supplier = self.model.supplier
        net = self.model.network
        rain = net.weather_rain_intensity

        try:
            path = net.find_shortest_path(
                str(self.store_node), str(supplier.location_node), mode="auto"
            )
            if path and len(path) >= 2:
                travel_time = net.calculate_path_travel_time(path, mode="auto")
                travel_time_min = travel_time / 60.0
            else:
                travel_time_min = 45.0
        except Exception:
            travel_time_min = 45.0

        if rain > 0.4:
            travel_time_min *= 2.0

        cost, qty = supplier.sell_stock(
            self.cash_balance, quantity=(1.0 - self.inventory)
        )
        self.cash_balance = max(0.0, self.cash_balance - cost)
        self.inventory = min(1.0, self.inventory + qty)

    def _adjust_pricing(self) -> None:
        avg = self.retail_memory.avg_revenue()
        if avg is None:
            return
        recent = list(self.retail_memory.sales_history)
        if len(recent) >= 2:
            mid = len(recent) // 2
            first_avg = sum(o.revenue for o in recent[:mid]) / mid if mid > 0 else avg
            second_avg = sum(o.revenue for o in recent[mid:]) / (len(recent) - mid)
            if second_avg < first_avg * 0.85:
                self.pricing_strategy = max(1.0, self.pricing_strategy - 0.05)
            elif second_avg > first_avg * 1.15:
                self.pricing_strategy = min(2.0, self.pricing_strategy + 0.05)

    def reset_for_new_day(self) -> None:
        pass


# ---------------------------------------------------------------------------
# MesaStoreStaff
# ---------------------------------------------------------------------------


class MesaStoreStaff(mesa.Agent):
    """Mesa-compatible store staff agent with shift-based commuting."""

    def __init__(
        self,
        model: UrbanModel,
        staff_id: int,
        home_node: str,
        store_node: str,
        shift_start: int = 9 * 60,
        shift_end: int = 17 * 60,
    ) -> None:
        super().__init__(model)
        self.staff_id = staff_id
        self.home_node = home_node
        self.store_node = store_node
        self.shift_start = shift_start
        self.shift_end = shift_end
        self.lateness_frustration: float = 0.0
        self.state: str = "AT_HOME"
        self._arrived_at_work: bool = False

    def step(self) -> None:
        current_time = self.model.sim_time_minutes % (24 * 60)

        if self.state == "AT_HOME":
            # Leave for work 60 min before shift
            if current_time >= (self.shift_start - 60):
                self.state = "COMMUTING"

        elif self.state == "COMMUTING":
            # Arrive at work (simplified — instant travel for now)
            if not self._arrived_at_work:
                self._arrived_at_work = True
                self.state = "AT_WORK"
                # Record arrival
                if current_time > self.shift_start:
                    self.lateness_frustration = min(
                        5.0, self.lateness_frustration + 0.5
                    )
                else:
                    self.lateness_frustration = max(
                        0.0, self.lateness_frustration - 0.2
                    )

        elif self.state == "AT_WORK":
            if current_time >= self.shift_end:
                self.state = "RETURNING"

        elif self.state == "RETURNING":
            self.state = "AT_HOME"

    def reset_for_new_day(self) -> None:
        self.state = "AT_HOME"
        self._arrived_at_work = False


# ---------------------------------------------------------------------------
# MesaDeliveryAgent
# ---------------------------------------------------------------------------


class MesaDeliveryAgent(mesa.Agent):
    """Mesa-compatible delivery gig worker."""

    def __init__(
        self,
        model: UrbanModel,
        delivery_id: int,
        home_node: str,
    ) -> None:
        super().__init__(model)
        self.delivery_id = delivery_id
        self.home_node = home_node
        self.current_location = home_node
        self.cash_balance: float = 200.0
        self.has_bike: bool = True
        self.completed_deliveries: int = 0
        self.earnings: float = 0.0

    @staticmethod
    def get_delivery_fee(base_fee: float, rain_intensity: float) -> float:
        if rain_intensity >= 0.5:
            return base_fee * (1.0 + 1.5 * rain_intensity)
        return base_fee

    def deliver_order(self, fee: float, destination_node: str) -> None:
        self.earnings += fee
        self.cash_balance += fee
        self.completed_deliveries += 1
        self.current_location = destination_node

    def step(self) -> None:
        # Delivery agents are reactive — they're dispatched by shopper agents
        pass

    def reset_for_new_day(self) -> None:
        self.current_location = self.home_node


# ---------------------------------------------------------------------------
# MesaEnforcementOfficer
# ---------------------------------------------------------------------------


class MesaEnforcementOfficer(mesa.Agent):
    """Mesa-compatible municipal enforcement officer patrolling street vendor zones."""

    def __init__(
        self,
        model: UrbanModel,
        officer_id: int,
        patrol_nodes: list[str],
    ) -> None:
        super().__init__(model)
        self.officer_id = officer_id
        self.patrol_nodes = patrol_nodes
        self.patrol_idx = 0
        self.current_location = patrol_nodes[0] if patrol_nodes else ""

    def step(self) -> None:
        if not self.patrol_nodes:
            return

        # Advance patrol location
        self.patrol_idx = (self.patrol_idx + 1) % len(self.patrol_nodes)
        self.current_location = self.patrol_nodes[self.patrol_idx]

        # Evict and fine any roadside vendor at the current node
        for stall in list(self.model.stalls.values()):
            if str(stall.current_location) == str(self.current_location) and not stall.is_bankrupt:
                stall.pay_fine(100.0)
                stall.evict()

    def reset_for_new_day(self) -> None:
        self.patrol_idx = 0
        if self.patrol_nodes:
            self.current_location = self.patrol_nodes[0]


# ---------------------------------------------------------------------------
# MesaDrainageWorker
# ---------------------------------------------------------------------------


class MesaDrainageWorker(mesa.Agent):
    """Mesa-compatible drainage worker reducing local flood congestion under rain."""

    def __init__(
        self,
        model: UrbanModel,
        worker_id: int,
        base_node: str,
    ) -> None:
        super().__init__(model)
        self.worker_id = worker_id
        self.base_node = base_node
        self.current_location = base_node
        self.is_busy: bool = False

    def step(self) -> None:
        net = self.model.network
        rain = net.weather_rain_intensity

        if rain > 0.1:
            self.is_busy = True
            # Mitigate local weather congestion
            net.drained_nodes.add(str(self.current_location))
        else:
            self.is_busy = False

    def reset_for_new_day(self) -> None:
        self.current_location = self.base_node
        self.is_busy = False


# ---------------------------------------------------------------------------
# MesaTrafficPolice
# ---------------------------------------------------------------------------


class MesaTrafficPolice(mesa.Agent):
    """Mesa-compatible traffic police officer boosting intersection capacities."""

    def __init__(
        self,
        model: UrbanModel,
        police_id: int,
        intersection_node: str,
    ) -> None:
        super().__init__(model)
        self.police_id = police_id
        self.intersection_node = intersection_node
        self.current_location = intersection_node

    def step(self) -> None:
        # Boost local intersection capacity
        self.model.network.traffic_police_nodes.add(str(self.current_location))

    def reset_for_new_day(self) -> None:
        pass
