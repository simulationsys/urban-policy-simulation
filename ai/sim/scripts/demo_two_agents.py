"""Detailed demonstration of advanced agent features:
1. Archetype-specific multi-leg activity scheduling.
2. Household vehicle mutual exclusion (car sharing).
3. Memory-driven schedule adaptation (earlier departure on delay).
4. Memory-driven mode frustration (switching modes on consecutive jams).

Usage:  python -m sim.scripts.demo_two_agents
"""

from __future__ import annotations

import numpy as np

from sim.agents.agent import Agent
from sim.agents.alternatives import default_alternatives
from sim.agents.household import Household
from sim.agents.memory import CommuteOutcome
from sim.agents.mode_choice import ModeAlternative, ModeChoiceModel
from sim.agents.modes import Mode, Occupation
from sim.agents.schedule import Activity, ActivitySchedule, ActivityType
from sim.agents.utility_weights import UtilityWeights


def make_priya() -> Agent:
    """Priya: A low-income student (highly cost-sensitive)."""
    home = 10
    school = 42
    rec = 99
    
    # 3-leg activity schedule: Home -> School (Education) -> Recreation -> Home
    schedule = ActivitySchedule(
        activities=[
            Activity(ActivityType.HOME, home, 0, 0),
            Activity(ActivityType.EDUCATION, school, 9 * 60 + 30, 5 * 60),
            Activity(ActivityType.RECREATION, rec, 15 * 60, 2 * 60),
        ],
        leave_home_min=9 * 60 + 30,
    )
    
    return Agent(
        id=1,
        home_node=home,
        work_node=None,
        income_bracket=1,
        age=21,
        household_id=100,
        occupation=Occupation.STUDENT,
        has_car=False,
        has_bike=True,
        has_metro_pass=True,
        schedule=schedule,
        weights=UtilityWeights(beta_cost=-0.08, beta_weather=-2.8),
        activity_locations={
            ActivityType.HOME: home,
            ActivityType.EDUCATION: school,
            ActivityType.RECREATION: rec,
        },
    )


def make_rohan() -> Agent:
    """Rohan: A high-income Office Executive (time-sensitive, comfort-driven)."""
    home = 11
    work = 43
    
    # 2-leg schedule: Home -> Work -> Home
    schedule = ActivitySchedule(
        activities=[
            Activity(ActivityType.HOME, home, 0, 0),
            Activity(ActivityType.WORK, work, 9 * 60, 9 * 60),
        ],
        leave_home_min=9 * 60,
    )
    
    return Agent(
        id=2,
        home_node=home,
        work_node=work,
        income_bracket=5,
        age=42,
        household_id=200,
        occupation=Occupation.OFFICE_EXECUTIVE,
        has_car=True,
        has_bike=False,
        has_metro_pass=False,
        schedule=schedule,
        weights=UtilityWeights.for_occupation(Occupation.OFFICE_EXECUTIVE),
        activity_locations={
            ActivityType.HOME: home,
            ActivityType.WORK: work,
        },
    )


def main() -> None:
    rng = np.random.default_rng(0)
    model = ModeChoiceModel(rng=rng)

    print("======================================================================")
    print("DEMO 1: ARCHETYPE MULTI-LEG SCHEDULES")
    print("======================================================================")
    priya = make_priya()
    rohan = make_rohan()

    for agent, name in [(priya, "Priya (Student)"), (rohan, "Rohan (Executive)")]:
        print(f"\n--- {name} ---")
        print(f"  Age: {agent.age}, Income Bracket: {agent.income_bracket}")
        print(f"  Occupation Archetype: {agent.occupation.value}")
        print("  Activity Schedule Legs:")
        legs = agent.schedule.get_legs()
        for orig, dest in legs:
            print(f"    - {orig.activity_type.value.upper()} (node {orig.location_node}) "
                  f"-> {dest.activity_type.value.upper()} (node {dest.location_node}) "
                  f"starting at {dest.start_time_min // 60:02d}:{dest.start_time_min % 60:02d}")

    print("\n======================================================================")
    print("DEMO 2: HOUSEHOLD VEHICLE RESOURCE MUTUAL EXCLUSION (CAR SHARING)")
    print("======================================================================")
    # Rohan and a new agent Amit (his brother, also working) share a single household car.
    shared_hh = Household(id=300, has_car=True, cars_owned=1, cars_available=1)
    
    rohan.household = shared_hh
    rohan.household_id = 300
    rohan.has_car = True
    
    amit = Agent(
        id=3,
        home_node=11,
        work_node=45,
        income_bracket=4,
        age=35,
        household_id=300,
        occupation=Occupation.OFFICE_EXECUTIVE,
        has_car=True,
        has_bike=False,
        schedule=ActivitySchedule(
            activities=[
                Activity(ActivityType.HOME, 11, 0, 0),
                Activity(ActivityType.WORK, 45, 8 * 60 + 30, 9 * 60),
            ],
            leave_home_min=8 * 60 + 30,
        ),
        weights=UtilityWeights.for_occupation(Occupation.OFFICE_EXECUTIVE),
        household=shared_hh,
    )
    
    shared_hh.member_ids = [rohan.id, amit.id]

    print("Initial state: 1 car owned, 1 car available in Household 300.")
    
    # 1. Amit decides first (leaves earlier at 8:30 AM)
    print(f"\nAmit available modes before requesting car: {[m.value for m in amit.available_modes()]}")
    amit_alts = default_alternatives(amit, distance_km=10.0)
    amit_choice = model.choose(amit, amit_alts, stochastic=False)
    print(f"Amit picks: {amit_choice.value}")
    
    if amit_choice == Mode.CAR:
        shared_hh.request_car()
        print(f"Amit claimed the household car! Available cars left: {shared_hh.cars_available}")
        
    # 2. Rohan decides later (leaves at 9:00 AM)
    print(f"\nRohan available modes when car is claimed: {[m.value for m in rohan.available_modes()]}")
    rohan_alts = default_alternatives(rohan, distance_km=10.0)
    rohan_choice = model.choose(rohan, rohan_alts, stochastic=False)
    print(f"Rohan picks: {rohan_choice.value} (Cannot drive car because it's already in use!)")
    
    # Reset car at end of day
    shared_hh.reset_daily_resources()
    print(f"\nEnd of day: Household resources reset. Available cars: {shared_hh.cars_available}")

    print("\n======================================================================")
    print("DEMO 3: MEMORY-DRIVEN SCHEDULE ADAPTATION")
    print("======================================================================")
    print(f"Priya initial target class start time: {priya.schedule.activities[1].start_time_min // 60:02d}:"
          f"{priya.schedule.activities[1].start_time_min % 60:02d}")
          
    # Priya experiences 3 consecutive highly delayed commutes on her bike (average ~20m, but takes 45m due to rain/traffic)
    print("Priya experiences 3 delayed commutes in a row...")
    priya.current_mode = Mode.BIKE
    for _ in range(3):
        # record historical outcomes to set the average
        priya.memory.record(CommuteOutcome(Mode.BIKE, travel_time_min=20.0, monetary_cost=0.0, comfort_score=0.4))
    
    # Now record 3 successive highly delayed outcomes
    for _ in range(3):
        priya.memory.record(CommuteOutcome(Mode.BIKE, travel_time_min=45.0, monetary_cost=0.0, comfort_score=0.2))
        
    # Trigger adaptation
    priya.adapt_behavior()
    print(f"Priya adapted target class start time (shifted 15 mins earlier): "
          f"{priya.schedule.activities[1].start_time_min // 60:02d}:"
          f"{priya.schedule.activities[1].start_time_min % 60:02d}")

    print("\n======================================================================")
    print("DEMO 4: MEMORY-DRIVEN MODE FRUSTRATION & SWITCHING")
    print("======================================================================")
    # Reset Priya to show frustration buildup dynamically
    priya = make_priya()
    # Assume a student subsidized metro fare of ₹5 to make Metro cost-viable
    priya_dry_alts = [
        ModeAlternative(Mode.BIKE, travel_time_min=20, monetary_cost=0, comfort_score=0.4),
        ModeAlternative(Mode.METRO, travel_time_min=30, monetary_cost=5, comfort_score=0.8),
    ]
    
    print(f"Priya Biking Frustration: {priya.memory.get_frustration(Mode.BIKE)}")
    choice_before = model.choose(priya, priya_dry_alts, stochastic=False)
    print(f"Priya Choice (before severe frustration): {choice_before.value}")
    
    # Priya experiences 3 normal and 3 bad commutes on Biking
    priya.current_mode = Mode.BIKE
    for _ in range(3):
        priya.memory.record(CommuteOutcome(Mode.BIKE, travel_time_min=20.0, monetary_cost=0.0, comfort_score=0.4))
    for _ in range(3):
        priya.memory.record(CommuteOutcome(Mode.BIKE, travel_time_min=45.0, monetary_cost=0.0, comfort_score=0.2))
    
    print(f"\nAfter 3 delayed commutes, Priya Biking Frustration is: {priya.memory.get_frustration(Mode.BIKE)}")
    choice_after = model.choose(priya, priya_dry_alts, stochastic=False)
    print(f"Priya Choice (after severe frustration): {choice_after.value} (Switched to Metro due to biking delay frustration!)")
    print("======================================================================\n")


if __name__ == "__main__":
    main()
