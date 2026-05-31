"""Informal retail agents — roadside stall owners.

Models three stall types (food, clothes, accessories) with:
- Dynamic location choice driven by frustration / foot-traffic memory.
- Inventory decay (perishability differs by stall type).
- Stochastic disruption events (weather, police clearance).

See ``gemini-code-1780254276846.md`` §1 for requirements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from sim.agents.modes import Occupation
from sim.agents.retail_memory import RetailMemory, SalesOutcome
from sim.agents.schedule import ActivitySchedule, ActivityType, Activity

NodeID = int


class StallType(str, Enum):
    """Categories of informal retail."""

    FOOD = "food"
    CLOTHES = "clothes"
    ACCESSORIES = "accessories"


# ------------------------------------------------------------------ #
# Base class
# ------------------------------------------------------------------ #


@dataclass
class StallOwner:
    """Base class for a roadside stall operator.

    Attributes:
        id: Unique agent identifier.
        home_node: Node where the stall owner lives.
        current_location: Node where the stall is currently set up.
        stall_type: The merchandise category.
        inventory: Normalised stock level (0.0 = empty, 1.0 = full).
        inventory_decay_rate: Fraction of inventory lost per tick (perishability).
        retail_memory: Rolling sales memory driving relocation decisions.
        schedule: Daily activity schedule.
        disruption_probability: Per-day chance of a disruption event.
    """

    id: int
    home_node: NodeID
    current_location: NodeID
    stall_type: StallType
    inventory: float = 1.0
    inventory_decay_rate: float = 0.05
    retail_memory: RetailMemory = field(default_factory=RetailMemory)
    schedule: ActivitySchedule = field(default_factory=ActivitySchedule)
    occupation: Occupation = Occupation.STALL_OWNER
    disruption_probability: float = 0.05
    is_disrupted_today: bool = False

    # ------------------------------------------------------------------ #
    # Location logic
    # ------------------------------------------------------------------ #

    def evaluate_location(self, foot_traffic: int) -> float:
        """Simple spatial utility: more foot traffic → higher utility.

        Returns a score in [0, ∞). Used to rank candidate vending locations.
        """
        return float(foot_traffic)

    def maybe_relocate(
        self,
        candidate_nodes: list[tuple[NodeID, int]],
        *,
        rng: np.random.Generator | None = None,
    ) -> NodeID | None:
        """If frustration is high enough, pick the best candidate node.

        Args:
            candidate_nodes: List of ``(node_id, foot_traffic)`` pairs.
            rng: Optional RNG for tie-breaking.

        Returns:
            The new ``NodeID`` the stall moves to, or ``None`` if it stays.
        """
        if not self.retail_memory.should_relocate():
            return None
        if not candidate_nodes:
            return None

        rng = rng or np.random.default_rng()
        # Rank by foot traffic utility (descending) with random tie-break
        scored = [
            (self.evaluate_location(ft), rng.random(), node)
            for node, ft in candidate_nodes
            if node != self.current_location
        ]
        if not scored:
            return None
        scored.sort(key=lambda t: (-t[0], t[1]))
        best_node = scored[0][2]

        self.current_location = best_node
        # Reset frustration partially after relocating
        self.retail_memory.frustration = max(
            0.0, self.retail_memory.frustration - 1.5,
        )
        return best_node

    # ------------------------------------------------------------------ #
    # Inventory
    # ------------------------------------------------------------------ #

    def decay_inventory(self) -> None:
        """Reduce inventory by the stall-specific decay rate each tick."""
        self.inventory = max(0.0, self.inventory - self.inventory_decay_rate)

    def restock(self, amount: float = 1.0) -> None:
        """Restock inventory to a given level (default: full)."""
        self.inventory = min(1.0, amount)

    # ------------------------------------------------------------------ #
    # Revenue helpers
    # ------------------------------------------------------------------ #

    def revenue_per_customer(self, base_price: float = 50.0) -> float:
        """Dynamic pricing: perishables get cheaper as inventory drops.

        For food stalls (high decay), this produces clearance-sale behaviour.
        For non-perishables the effect is negligible.
        """
        # Price drops linearly with remaining inventory for high-decay goods
        decay_discount = 1.0 - (self.inventory_decay_rate * (1.0 - self.inventory))
        return base_price * max(0.3, decay_discount)

    # ------------------------------------------------------------------ #
    # Disruption
    # ------------------------------------------------------------------ #

    def apply_disruption(self, rng: np.random.Generator | None = None) -> bool:
        """Roll for a daily disruption event (weather, police, etc.).

        If disrupted:
        - The stall is closed for the day.
        - Frustration spikes by +1.5.
        - A zero-revenue SalesOutcome is recorded.

        Returns:
            True if a disruption occurred.
        """
        rng = rng or np.random.default_rng()
        if rng.random() < self.disruption_probability:
            self.is_disrupted_today = True
            self.retail_memory.record_disruption(self.current_location)
            return True
        self.is_disrupted_today = False
        return False

    # ------------------------------------------------------------------ #
    # Daily lifecycle
    # ------------------------------------------------------------------ #

    def begin_day(self, rng: np.random.Generator | None = None) -> None:
        """Called at the start of each simulated day.

        Checks for disruption; if none, decays inventory and builds schedule.
        """
        self.is_disrupted_today = False
        if self.apply_disruption(rng):
            return
        self.decay_inventory()
        # Build a simple vending schedule: Home → Vending → Home
        self.schedule = ActivitySchedule(
            activities=[
                Activity(ActivityType.HOME, self.home_node, 0, 6 * 60),
                Activity(ActivityType.VENDING, self.current_location, 6 * 60, 12 * 60),
                Activity(ActivityType.HOME, self.home_node, 18 * 60, 6 * 60),
            ],
            leave_home_min=6 * 60,
        )


# ------------------------------------------------------------------ #
# Concrete subclasses
# ------------------------------------------------------------------ #


@dataclass
class FoodStallOwner(StallOwner):
    """Fast-perishable food stall. High inventory decay, weather-vulnerable."""

    stall_type: StallType = StallType.FOOD
    inventory_decay_rate: float = 0.15
    disruption_probability: float = 0.05


@dataclass
class ClothesStallOwner(StallOwner):
    """Clothes stall. Low decay, higher police-clearance risk."""

    stall_type: StallType = StallType.CLOTHES
    inventory_decay_rate: float = 0.02
    disruption_probability: float = 0.08


@dataclass
class AccessoriesStallOwner(StallOwner):
    """Accessories stall. Negligible decay, mid-range disruption risk."""

    stall_type: StallType = StallType.ACCESSORIES
    inventory_decay_rate: float = 0.01
    disruption_probability: float = 0.06
