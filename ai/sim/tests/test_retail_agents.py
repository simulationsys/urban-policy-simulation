"""Tests for the retail / economic agent extensions.

Covers:
- Stall owner relocation on high frustration.
- Food vs. clothes inventory decay rates.
- Disruption events spiking frustration.
- Store staff lateness frustration.
- Shop choice income sensitivity (low-income prefers cheap stalls).
- Purchase interaction updating both agents.
"""

from __future__ import annotations

import numpy as np
import pytest

from sim.agents import (
    Agent,
    FoodStallOwner,
    ClothesStallOwner,
    AccessoriesStallOwner,
    StoreManager,
    StoreStaff,
    ShopAlternative,
    ShopChoiceModel,
    ShopType,
    process_purchase,
)
from sim.agents.retail_memory import RetailMemory, SalesOutcome


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #


def _make_food_stall(node: int = 10) -> FoodStallOwner:
    return FoodStallOwner(id=100, home_node=0, current_location=node)


def _make_clothes_stall(node: int = 20) -> ClothesStallOwner:
    return ClothesStallOwner(id=101, home_node=0, current_location=node)


def _make_agent(income: int = 3) -> Agent:
    return Agent(
        id=1,
        home_node=0,
        work_node=1,
        income_bracket=income,
        age=30,
        household_id=1,
    )


# ------------------------------------------------------------------ #
# 1. Stall owner relocates when frustration exceeds threshold
# ------------------------------------------------------------------ #


def test_stall_owner_relocates_on_high_frustration() -> None:
    """Core requirement: stall should move when frustration >= 2.0."""
    stall = _make_food_stall(node=10)

    # Manually raise frustration above the threshold
    stall.retail_memory.frustration = 2.5

    candidates = [(20, 80), (30, 120), (40, 50)]  # (node_id, foot_traffic)
    new_node = stall.maybe_relocate(candidates, rng=np.random.default_rng(42))

    assert new_node is not None, "Stall should relocate when frustrated"
    assert new_node == 30, "Should pick the highest foot-traffic node"
    assert stall.current_location == 30


def test_stall_owner_stays_when_not_frustrated() -> None:
    """Stall should NOT relocate when frustration is below threshold."""
    stall = _make_food_stall(node=10)
    stall.retail_memory.frustration = 1.0  # below 2.0 threshold

    candidates = [(20, 80), (30, 120)]
    new_node = stall.maybe_relocate(candidates)

    assert new_node is None, "Stall should stay when frustration is low"
    assert stall.current_location == 10


# ------------------------------------------------------------------ #
# 2. Food stall inventory decays faster than clothes
# ------------------------------------------------------------------ #


def test_food_stall_inventory_decays_faster_than_clothes() -> None:
    food = _make_food_stall()
    clothes = _make_clothes_stall()

    # Both start at full inventory
    assert food.inventory == 1.0
    assert clothes.inventory == 1.0

    # Decay for 5 ticks
    for _ in range(5):
        food.decay_inventory()
        clothes.decay_inventory()

    # Food (rate=0.15) should be much lower than clothes (rate=0.02)
    assert food.inventory < clothes.inventory
    assert food.inventory == pytest.approx(1.0 - 5 * 0.15, abs=1e-9)
    assert clothes.inventory == pytest.approx(1.0 - 5 * 0.02, abs=1e-9)


# ------------------------------------------------------------------ #
# 3. Disruption spikes frustration
# ------------------------------------------------------------------ #


def test_disruption_spikes_frustration() -> None:
    stall = _make_food_stall()
    initial_frustration = stall.retail_memory.frustration

    # Force a disruption by using a rigged RNG
    # disruption_probability for food stall is 0.05
    # We use a generator that returns a value < 0.05
    rng = np.random.default_rng(42)
    # Instead, directly call record_disruption for deterministic testing
    stall.retail_memory.record_disruption(stall.current_location)

    assert stall.retail_memory.frustration == initial_frustration + 1.5
    assert len(stall.retail_memory.sales_history) == 1
    assert stall.retail_memory.sales_history[0].revenue == 0.0


# ------------------------------------------------------------------ #
# 4. Store staff lateness frustration
# ------------------------------------------------------------------ #


def test_store_staff_lateness_frustration() -> None:
    staff = StoreStaff(id=200, home_node=0, store_node=5)
    manager = StoreManager(id=300, store_node=5, staff_ids=[200])

    # Assign a shift: 09:00 - 17:00
    manager.assign_shifts([staff])

    assert staff.assigned_shift is not None
    assert staff.assigned_shift.start_time_min == 9 * 60

    # Staff arrives late
    staff.record_arrival(actual_arrival_min=9 * 60 + 15)  # 15 min late
    assert staff.lateness_frustration == 0.5

    # Another late arrival
    staff.record_arrival(actual_arrival_min=9 * 60 + 5)
    assert staff.lateness_frustration == 1.0

    # On-time arrival → cools down
    staff.record_arrival(actual_arrival_min=8 * 60 + 50)
    assert staff.lateness_frustration == pytest.approx(0.8)


# ------------------------------------------------------------------ #
# 5. Shop choice: low-income agent prefers cheap stall
# ------------------------------------------------------------------ #


def test_shop_choice_income_sensitivity() -> None:
    model = ShopChoiceModel(rng=np.random.default_rng(0))

    low_income = _make_agent(income=1)
    high_income = _make_agent(income=5)

    alts = [
        ShopAlternative(
            shop_id=1,
            shop_type=ShopType.FORMAL_STORE,
            distance_km=2.0,
            travel_time_min=15,
            price_level=0.8,   # expensive
            product_match=0.9,
        ),
        ShopAlternative(
            shop_id=2,
            shop_type=ShopType.FOOD_STALL,
            distance_km=1.0,
            travel_time_min=8,
            price_level=0.2,   # cheap
            product_match=0.7,
        ),
    ]

    low_choice = model.choose(low_income, alts, stochastic=False)
    high_choice = model.choose(high_income, alts, stochastic=False)

    # Low-income agent should prefer the cheap stall
    assert low_choice.shop_type == ShopType.FOOD_STALL
    # High-income agent should prefer the formal store (formality bonus + low price sensitivity)
    assert high_choice.shop_type == ShopType.FORMAL_STORE


# ------------------------------------------------------------------ #
# 6. Purchase interaction updates both agents
# ------------------------------------------------------------------ #


def test_purchase_interaction_updates_both_agents() -> None:
    shopper = _make_agent(income=3)
    stall = _make_food_stall()

    result = process_purchase(shopper, stall, base_price=50.0, foot_traffic=25)

    assert result.success is True
    assert result.stall_revenue > 0
    assert result.shopper_utility_gain != 0.0

    # Stall's memory should now have one recorded sale
    assert len(stall.retail_memory.sales_history) == 1
    assert stall.retail_memory.sales_history[0].customers_served == 1

    # Stall inventory should have decreased
    assert stall.inventory < 1.0


def test_purchase_fails_when_disrupted() -> None:
    stall = _make_food_stall()
    stall.is_disrupted_today = True
    shopper = _make_agent()

    result = process_purchase(shopper, stall)

    assert result.success is False
    assert result.reason == "Stall is disrupted today"


def test_purchase_fails_when_out_of_stock() -> None:
    stall = _make_food_stall()
    stall.inventory = 0.0
    shopper = _make_agent()

    result = process_purchase(shopper, stall)

    assert result.success is False
    assert result.reason == "Stall is out of stock"
