"""Shopper ↔ StallOwner interaction logic.

Demonstrates how a citizen agent (shopper) purchasing from a stall owner
updates both agents' memory and frustration metrics.

See ``gemini-code-1780254276846.md`` §Output Requirements #2.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.agents.agent import Agent
from sim.agents.retail_memory import SalesOutcome
from sim.agents.stall_owner import StallOwner


@dataclass
class PurchaseResult:
    """Outcome of a shopper purchasing from a stall.

    Attributes:
        success: Whether the purchase was completed.
        shopper_utility_gain: Utility change for the shopper (positive = good deal).
        stall_revenue: Revenue earned by the stall owner from this sale.
        reason: Human-readable reason if the purchase failed.
    """

    success: bool
    shopper_utility_gain: float
    stall_revenue: float
    reason: str = ""


def process_purchase(
    shopper: Agent,
    stall: StallOwner,
    *,
    base_price: float = 50.0,
    foot_traffic: int = 20,
) -> PurchaseResult:
    """Simulate a single purchase interaction between a shopper and stall owner.

    Flow:
    1. If the stall is disrupted or out of stock → purchase fails.
    2. Stall calculates revenue-per-customer (dynamic pricing).
    3. Shopper's utility gain is computed based on price vs. income.
    4. Stall records the sale, which updates its frustration/memory.

    Args:
        shopper: The citizen agent making the purchase.
        stall: The stall owner agent selling goods.
        base_price: Base price before dynamic adjustments.
        foot_traffic: Current foot traffic at the stall's location.

    Returns:
        A ``PurchaseResult`` describing the outcome.
    """
    # Guard: disrupted stalls can't sell
    if stall.is_disrupted_today:
        return PurchaseResult(
            success=False,
            shopper_utility_gain=0.0,
            stall_revenue=0.0,
            reason="Stall is disrupted today",
        )

    # Guard: out of stock
    if stall.inventory <= 0.0:
        return PurchaseResult(
            success=False,
            shopper_utility_gain=0.0,
            stall_revenue=0.0,
            reason="Stall is out of stock",
        )

    # --- Transaction ---
    price = stall.revenue_per_customer(base_price)

    # Shopper utility: cheaper is better, scaled by income sensitivity
    cost_scale = (6 - shopper.income_bracket) / 3.0
    shopper_utility = 1.0 - (price / base_price) * cost_scale * 0.5

    # Stall records the sale
    stall.retail_memory.record_sales(
        SalesOutcome(
            revenue=price,
            customers_served=1,
            foot_traffic=foot_traffic,
            location_node=stall.current_location,
        )
    )

    # Reduce stall inventory slightly per sale
    stall.inventory = max(0.0, stall.inventory - 0.05)

    return PurchaseResult(
        success=True,
        shopper_utility_gain=shopper_utility,
        stall_revenue=price,
    )
