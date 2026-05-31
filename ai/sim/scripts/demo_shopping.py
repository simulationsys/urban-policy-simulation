"""Demonstration of economic & retail agent decision-making:
1. Shop choice: Low-income vs. high-income agent picking where to shop.
2. Stall owner lifecycle: Inventory decay, disruption, frustration, relocation.
3. Store staff: Shift assignment and lateness frustration.
4. Purchase interaction: Shopper ↔ StallOwner with mutual memory updates.
5. Multi-day simulation: Stall owner frustration building over bad days.

Usage:  python -m sim.scripts.demo_shopping
"""

from __future__ import annotations

import numpy as np

from sim.agents.agent import Agent
from sim.agents.modes import Occupation
from sim.agents.retail_interaction import process_purchase
from sim.agents.retail_memory import RetailMemory, SalesOutcome
from sim.agents.schedule import Activity, ActivitySchedule, ActivityType
from sim.agents.shop_choice import (
    ShopAlternative,
    ShopChoiceModel,
    ShoppingNeed,
    ShopType,
)
from sim.agents.stall_owner import (
    FoodStallOwner,
    ClothesStallOwner,
    AccessoriesStallOwner,
    StallType,
)
from sim.agents.store_agents import StoreManager, StoreStaff
from sim.agents.utility_weights import UtilityWeights


# ====================================================================== #
#  Helper factories
# ====================================================================== #


def make_asha() -> Agent:
    """Asha: A low-income blue-collar worker. Very price-sensitive."""
    return Agent(
        id=1,
        home_node=5,
        work_node=15,
        income_bracket=1,
        age=34,
        household_id=10,
        occupation=Occupation.BLUE_COLLAR_WORKER,
        has_bike=True,
        shopping_needs=[ShoppingNeed(product_type="food", urgency=0.9)],
    )


def make_vikram() -> Agent:
    """Vikram: A high-income executive. Prefers formal retail, convenience."""
    return Agent(
        id=2,
        home_node=8,
        work_node=30,
        income_bracket=5,
        age=45,
        household_id=20,
        occupation=Occupation.OFFICE_EXECUTIVE,
        has_car=True,
        weights=UtilityWeights.for_occupation(Occupation.OFFICE_EXECUTIVE),
        shopping_needs=[ShoppingNeed(product_type="clothes", urgency=0.6)],
    )


# ====================================================================== #
#  DEMO 1: Income-based shop destination choice
# ====================================================================== #


def demo_shop_choice() -> None:
    print("=" * 72)
    print("  DEMO 1: SHOP DESTINATION CHOICE (Income Sensitivity)")
    print("=" * 72)

    shop_model = ShopChoiceModel(rng=np.random.default_rng(42))
    asha = make_asha()
    vikram = make_vikram()

    # Same set of alternatives available to both agents
    alternatives = [
        ShopAlternative(
            shop_id=101,
            shop_type=ShopType.FORMAL_STORE,
            distance_km=1.5,
            travel_time_min=12,
            price_level=0.80,
            product_match=0.95,
        ),
        ShopAlternative(
            shop_id=201,
            shop_type=ShopType.FOOD_STALL,
            distance_km=1.0,
            travel_time_min=8,
            price_level=0.15,
            product_match=0.7,
        ),
        ShopAlternative(
            shop_id=202,
            shop_type=ShopType.CLOTHES_STALL,
            distance_km=1.8,
            travel_time_min=14,
            price_level=0.25,
            product_match=0.6,
        ),
    ]

    for agent, name in [(asha, "Asha (Low-income)"), (vikram, "Vikram (High-income)")]:
        print(f"\n--- {name} ---")
        print(f"  Income Bracket: {agent.income_bracket}/5")
        print(f"  Shopping Need:  {agent.shopping_needs[0].product_type} "
              f"(urgency: {agent.shopping_needs[0].urgency})")
        print()

        # Show utility breakdown for each alternative
        print(f"  {'SHOP':20s} | {'TYPE':15s} | {'PRICE':6s} | {'DIST':5s} | {'UTILITY':>8s}")
        print(f"  {'-' * 62}")

        for alt in alternatives:
            u = shop_model.utility(agent, alt)
            print(f"  Shop #{alt.shop_id:03d}           | {alt.shop_type.value:15s} | "
                  f"{alt.price_level:5.2f} | {alt.distance_km:4.1f} | {u:>8.4f}")

        chosen = shop_model.choose(agent, alternatives, stochastic=False)
        print(f"\n  ➜ CHOSEN: Shop #{chosen.shop_id} ({chosen.shop_type.value})")

    print()


# ====================================================================== #
#  DEMO 2: Stall owner lifecycle (inventory, disruption, relocation)
# ====================================================================== #


def demo_stall_lifecycle() -> None:
    print("=" * 72)
    print("  DEMO 2: STALL OWNER LIFECYCLE (Decay, Disruption, Relocation)")
    print("=" * 72)

    rng = np.random.default_rng(7)
    food = FoodStallOwner(id=301, home_node=0, current_location=50)
    clothes = ClothesStallOwner(id=302, home_node=0, current_location=60)
    accessories = AccessoriesStallOwner(id=303, home_node=0, current_location=70)

    stalls = [
        (food, "Food Stall (Raju)"),
        (clothes, "Clothes Stall (Meena)"),
        (accessories, "Accessories Stall (Sunita)"),
    ]

    print(f"\n  {'STALL':28s} | {'DECAY RATE':10s} | {'DISRUPT %':9s}")
    print(f"  {'-' * 52}")
    for stall, name in stalls:
        print(f"  {name:28s} | {stall.inventory_decay_rate:10.2f} | "
              f"{stall.disruption_probability * 100:8.1f}%")

    # Simulate 5 ticks of inventory decay
    print(f"\n  --- Inventory after 5 ticks of decay ---")
    for stall, name in stalls:
        for _ in range(5):
            stall.decay_inventory()
        print(f"  {name:28s} | Inventory: {stall.inventory:.2f} / 1.00")

    # Show clearance pricing effect on food stall
    print(f"\n  --- Dynamic pricing (base ₹50) ---")
    food_full = FoodStallOwner(id=310, home_node=0, current_location=50, inventory=1.0)
    food_low = FoodStallOwner(id=311, home_node=0, current_location=50, inventory=0.2)
    print(f"  Food stall (full inventory):  ₹{food_full.revenue_per_customer(50.0):.2f}")
    print(f"  Food stall (20% inventory):   ₹{food_low.revenue_per_customer(50.0):.2f}")
    print(f"  Clothes stall (any level):    ₹{clothes.revenue_per_customer(50.0):.2f}")

    # Demonstrate disruption
    print(f"\n  --- Disruption event ---")
    food_d = FoodStallOwner(id=320, home_node=0, current_location=50)
    print(f"  Before disruption → Frustration: {food_d.retail_memory.frustration:.1f}")
    food_d.retail_memory.record_disruption(food_d.current_location)
    print(f"  After disruption  → Frustration: {food_d.retail_memory.frustration:.1f}  "
          f"(spiked by +1.5)")

    # Demonstrate relocation
    print(f"\n  --- Relocation decision ---")
    food_r = FoodStallOwner(id=330, home_node=0, current_location=50)
    food_r.retail_memory.frustration = 2.5  # above threshold of 2.0

    candidates = [(51, 30), (52, 120), (53, 75), (54, 45)]
    print(f"  Current location: Node {food_r.current_location}")
    print(f"  Frustration: {food_r.retail_memory.frustration:.1f} (threshold: 2.0)")
    print(f"  Candidate nodes: {[(n, f'traffic={t}') for n, t in candidates]}")

    new_loc = food_r.maybe_relocate(candidates, rng=rng)
    print(f"  ➜ RELOCATED to Node {new_loc} (highest foot traffic)")
    print(f"  Post-move frustration: {food_r.retail_memory.frustration:.1f} (partially reset)")

    print()


# ====================================================================== #
#  DEMO 3: Store manager assigns shifts, staff lateness
# ====================================================================== #


def demo_store_operations() -> None:
    print("=" * 72)
    print("  DEMO 3: FORMAL STORE OPERATIONS (Shifts & Lateness)")
    print("=" * 72)

    manager = StoreManager(id=400, store_node=25, staff_ids=[401, 402])

    ankit = StoreStaff(id=401, home_node=5, store_node=25)
    deepa = StoreStaff(id=402, home_node=12, store_node=25)

    # Manager assigns shifts
    shifts = manager.assign_shifts([ankit, deepa])

    print(f"\n  Store Manager #{manager.id} at Node {manager.store_node}")
    print(f"  Pricing strategy: {manager.pricing_strategy:.1f}x markup")
    print(f"  Restock day: {'Mon Tue Wed Thu Fri Sat Sun'.split()[manager.restock_day]}")

    print(f"\n  --- Assigned Shifts ---")
    for staff, name in [(ankit, "Ankit"), (deepa, "Deepa")]:
        s = staff.assigned_shift
        assert s is not None
        start = f"{s.start_time_min // 60:02d}:{s.start_time_min % 60:02d}"
        end = f"{s.end_time_min // 60:02d}:{s.end_time_min % 60:02d}"
        leave = f"{staff.schedule.leave_home_min // 60:02d}:{staff.schedule.leave_home_min % 60:02d}"
        print(f"  {name}: Shift {start} – {end} | Leaves home at {leave}")

    # Simulate 5 days of commuting with varying arrival times
    print(f"\n  --- Ankit's commute over 5 days ---")
    print(f"  {'DAY':5s} | {'ARRIVE':8s} | {'ON TIME?':10s} | {'FRUST':>6s}")
    print(f"  {'-' * 38}")

    arrival_times = [8 * 60 + 55, 9 * 60 + 10, 9 * 60 + 20, 8 * 60 + 50, 9 * 60 + 5]
    for day, arrival in enumerate(arrival_times, 1):
        shift_start = ankit.assigned_shift.start_time_min  # type: ignore[union-attr]
        on_time = "✅ Yes" if arrival <= shift_start else "❌ No "
        ankit.record_arrival(arrival)
        arr_str = f"{arrival // 60:02d}:{arrival % 60:02d}"
        print(f"  Day {day} | {arr_str:8s} | {on_time:10s} | {ankit.lateness_frustration:>5.1f}")

    print()


# ====================================================================== #
#  DEMO 4: Purchase interaction (Shopper ↔ StallOwner)
# ====================================================================== #


def demo_purchase_interaction() -> None:
    print("=" * 72)
    print("  DEMO 4: PURCHASE INTERACTION (Shopper ↔ Stall Owner)")
    print("=" * 72)

    asha = make_asha()
    food_stall = FoodStallOwner(id=301, home_node=0, current_location=50)

    print(f"\n  Shopper: Asha (income bracket {asha.income_bracket})")
    print(f"  Stall:   Food Stall #{food_stall.id} at Node {food_stall.current_location}")
    print(f"  Stall inventory: {food_stall.inventory:.2f}")
    print(f"  Stall frustration: {food_stall.retail_memory.frustration:.1f}")

    # Execute 3 purchases
    print(f"\n  --- Purchases ---")
    print(f"  {'#':3s} | {'SUCCESS':8s} | {'REVENUE':>8s} | {'SHOPPER +U':>10s} | "
          f"{'INVENTORY':>9s} | {'FRUST':>5s}")
    print(f"  {'-' * 56}")

    for i in range(1, 4):
        result = process_purchase(asha, food_stall, base_price=50.0, foot_traffic=30)
        print(f"  {i:3d} | {'Yes':8s} | ₹{result.stall_revenue:>6.2f} | "
              f"{result.shopper_utility_gain:>+9.4f} | "
              f"{food_stall.inventory:>8.2f} | {food_stall.retail_memory.frustration:>5.1f}")

    # Now simulate a disruption
    print(f"\n  --- Disruption event hits the stall! ---")
    food_stall.is_disrupted_today = True
    result = process_purchase(asha, food_stall)
    print(f"  Purchase attempt: {result.reason}")

    print()


# ====================================================================== #
#  DEMO 5: Multi-day frustration build-up and relocation
# ====================================================================== #


def demo_multi_day_frustration() -> None:
    print("=" * 72)
    print("  DEMO 5: MULTI-DAY SIMULATION (Frustration → Relocation)")
    print("=" * 72)

    rng = np.random.default_rng(99)
    stall = FoodStallOwner(id=500, home_node=0, current_location=50)

    # Candidate locations with foot traffic
    candidates = [
        (51, 40), (52, 90), (53, 150), (54, 60),
    ]

    # Simulate 10 days: first 7 days have declining revenue to build frustration
    daily_revenues = [200, 180, 120, 80, 50, 30, 20, 250, 300, 280]

    print(f"\n  Starting location: Node {stall.current_location}")
    print(f"\n  {'DAY':5s} | {'REVENUE':>8s} | {'FRUST':>6s} | {'RELOCATE?':>10s} | {'LOCATION':>8s}")
    print(f"  {'-' * 50}")

    for day, revenue in enumerate(daily_revenues, 1):
        stall.retail_memory.record_sales(
            SalesOutcome(
                revenue=revenue,
                customers_served=int(revenue / 50),
                foot_traffic=int(revenue / 10),
                location_node=stall.current_location,
            )
        )

        # Check for relocation
        new_loc = stall.maybe_relocate(candidates, rng=rng)
        relocated = f"→ Node {new_loc}" if new_loc else "No"

        print(f"  Day {day:2d} | ₹{revenue:>6.0f} | {stall.retail_memory.frustration:>5.1f} | "
              f"{relocated:>10s} | Node {stall.current_location}")

    print(f"\n  Final location: Node {stall.current_location}")
    print(f"  Final frustration: {stall.retail_memory.frustration:.1f}")
    print()


# ====================================================================== #
#  Main
# ====================================================================== #


def main() -> None:
    demo_shop_choice()
    demo_stall_lifecycle()
    demo_store_operations()
    demo_purchase_interaction()
    demo_multi_day_frustration()

    print("=" * 72)
    print("  ALL DEMOS COMPLETED SUCCESSFULLY ✅")
    print("=" * 72)


if __name__ == "__main__":
    main()
