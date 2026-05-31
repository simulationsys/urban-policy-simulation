"""MNL-based shop destination choice for citizen agents.

Mirrors the design of ``mode_choice.py``: a utility function scores each
shopping alternative, and a Gumbel-max draw picks the winner (MNL).

Income interaction uses the same ``(6 - income_bracket) / 3`` scaling so
lower-income agents are more price-sensitive and prefer cheaper stalls.

See ``gemini-code-1780254276846.md`` §3 for requirements.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from sim.agents.agent import Agent


class ShopType(str, Enum):
    """Destination type for a shopping trip."""

    FORMAL_STORE = "formal_store"
    FOOD_STALL = "food_stall"
    CLOTHES_STALL = "clothes_stall"
    ACCESSORIES_STALL = "accessories_stall"


@dataclass
class ShoppingNeed:
    """A pending shopping need carried by a citizen agent.

    Attributes:
        product_type: What the agent wants to buy (e.g. "food", "clothes").
        urgency: How urgently the agent needs the product (0.0 = low, 1.0 = high).
    """

    product_type: str
    urgency: float = 0.5


@dataclass
class ShopAlternative:
    """One candidate shopping destination scored by ``ShopChoiceModel``.

    Attributes:
        shop_id: Unique ID of the shop / stall.
        shop_type: Category of the retail destination.
        distance_km: Euclidean or network distance from the agent's current node.
        travel_time_min: Estimated travel time to the shop.
        price_level: Relative price (0 = cheap, 1 = expensive).
        product_match: How well the shop's stock matches the agent's need (0..1).
    """

    shop_id: int
    shop_type: ShopType
    distance_km: float
    travel_time_min: float
    price_level: float  # 0..1; stalls are cheaper
    product_match: float  # 0..1


@dataclass
class ShopChoiceWeights:
    """Utility coefficients for the shop-destination MNL model."""

    beta_price: float = -0.06
    beta_distance: float = -0.10
    beta_travel_time: float = -0.04
    beta_product: float = 0.8
    beta_formality: float = 0.3  # positive = prefers formal stores


class ShopChoiceModel:
    """Multinomial-logit model for choosing *where* to shop.

    U(shop) = β_price × price_level × income_scale
            + β_distance × distance_km
            + β_travel_time × travel_time_min
            + β_product × product_match
            + β_formality × is_formal × income_bonus
            + ε  (Gumbel noise for stochastic draw)

    Higher-income agents tolerate higher prices and prefer formal stores.
    """

    def __init__(
        self,
        weights: ShopChoiceWeights | None = None,
        rng: np.random.Generator | None = None,
    ) -> None:
        self.w = weights or ShopChoiceWeights()
        self.rng = rng or np.random.default_rng()

    def utility(self, agent: Agent, alt: ShopAlternative) -> float:
        """Deterministic utility of a shopping alternative for an agent."""
        w = self.w
        # Lower-income agents weight price more heavily (same pattern as mode_choice)
        cost_scale = (6 - agent.income_bracket) / 3.0

        # Formal-store preference scales with income (rich prefer formal)
        is_formal = 1.0 if alt.shop_type == ShopType.FORMAL_STORE else 0.0
        income_bonus = agent.income_bracket / 5.0  # 0.2 … 1.0

        return (
            w.beta_price * alt.price_level * cost_scale
            + w.beta_distance * alt.distance_km
            + w.beta_travel_time * alt.travel_time_min
            + w.beta_product * alt.product_match
            + w.beta_formality * is_formal * income_bonus
        )

    def choose(
        self,
        agent: Agent,
        alts: list[ShopAlternative],
        *,
        stochastic: bool = True,
    ) -> ShopAlternative:
        """Pick the best shopping alternative via MNL (Gumbel-max trick).

        Args:
            agent: The citizen agent shopping.
            alts: Available shopping destinations.
            stochastic: If False, pick the deterministic argmax.

        Returns:
            The chosen ``ShopAlternative``.

        Raises:
            ValueError: If ``alts`` is empty.
        """
        if not alts:
            raise ValueError("No shop alternatives provided")

        utilities = np.array([self.utility(agent, a) for a in alts], dtype=float)

        if stochastic:
            gumbel = self.rng.gumbel(size=utilities.shape)
            idx = int(np.argmax(utilities + gumbel))
        else:
            idx = int(np.argmax(utilities))

        return alts[idx]
