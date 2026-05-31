"""Comprehensive sweep smoke test.

Tests all five occupational archetypes under a full sweep of parameter conditions:
- Trip distances (Short: 1.5km, Medium: 7.5km, Long: 18.0km)
- Weather conditions (Dry: 0.0, Light Rain: 0.4, Heavy Rain: 1.0)
- Household car resource constraints (Car available vs. car claimed/unavailable)
- Frustration memory states (Fresh/No frustration vs. Stressed/High frustration)

Usage: python -m sim.scripts.smoke_test_conditions
"""

from __future__ import annotations

import numpy as np

from sim.agents.agent import Agent
from sim.agents.alternatives import default_alternatives
from sim.agents.household import Household
from sim.agents.memory import CommuteOutcome
from sim.agents.mode_choice import ModeChoiceModel
from sim.agents.modes import Mode, Occupation
from sim.agents.schedule import Activity, ActivitySchedule, ActivityType
from sim.agents.utility_weights import UtilityWeights


def build_test_agents() -> dict[Occupation, Agent]:
    """Build representative agents for each of the 5 archetypes."""
    # Shared household reference for car sharing tests
    hh = Household(id=500, has_car=True, cars_owned=1, cars_available=1)
    
    agents = {
        Occupation.OFFICE_EXECUTIVE: Agent(
            id=1,
            home_node=10,
            work_node=20,
            income_bracket=5,
            age=40,
            household_id=500,
            occupation=Occupation.OFFICE_EXECUTIVE,
            has_car=True,
            weights=UtilityWeights.for_occupation(Occupation.OFFICE_EXECUTIVE),
            household=hh,
        ),
        Occupation.STUDENT: Agent(
            id=2,
            home_node=11,
            work_node=None,
            income_bracket=1,
            age=20,
            household_id=501,
            occupation=Occupation.STUDENT,
            has_bike=True,
            weights=UtilityWeights.for_occupation(Occupation.STUDENT),
        ),
        Occupation.BLUE_COLLAR_WORKER: Agent(
            id=3,
            home_node=12,
            work_node=22,
            income_bracket=3,
            age=32,
            household_id=502,
            occupation=Occupation.BLUE_COLLAR_WORKER,
            has_bike=True,
            weights=UtilityWeights.for_occupation(Occupation.BLUE_COLLAR_WORKER),
        ),
        Occupation.GIG_WORKER: Agent(
            id=4,
            home_node=13,
            work_node=23,
            income_bracket=2,
            age=27,
            household_id=503,
            occupation=Occupation.GIG_WORKER,
            has_bike=True,
            weights=UtilityWeights.for_occupation(Occupation.GIG_WORKER),
        ),
        Occupation.RETIRED_CITIZEN: Agent(
            id=5,
            home_node=14,
            work_node=None,
            income_bracket=3,
            age=68,
            household_id=504,
            occupation=Occupation.RETIRED_CITIZEN,
            weights=UtilityWeights.for_occupation(Occupation.RETIRED_CITIZEN),
        ),
    }
    
    hh.member_ids = [1]
    return agents


def main() -> None:
    rng = np.random.default_rng(42)
    model = ModeChoiceModel(rng=rng)
    
    distances = [1.5, 7.5, 18.0]
    rains = [0.0, 0.4, 1.0]
    car_shares = [True, False]  # True = car available, False = car claimed
    frustrations = [0.0, 3.0]    # 0 = fresh, 3 = highly frustrated with preferred mode
    
    print("======================================================================")
    print("      COMPREHENSIVE SWEEP SMOKE TEST - URBAN POLICY SIMULATION        ")
    print("======================================================================\n")
    
    agents = build_test_agents()
    
    # We will print a clean table summarizing the results of our sweeps
    print(f"{'ARCHETYPE':22s} | {'DIST':5s} | {'RAIN':4s} | {'CAR_OK':6s} | {'FRUST':5s} | {'CHOSEN MODE':11s}")
    print("-" * 72)
    
    total_runs = 0
    successful_runs = 0
    
    for occ, agent in agents.items():
        for dist in distances:
            # Skip walks if distance is too long (already handled in alternatives)
            for rain in rains:
                for car_ok in car_shares:
                    # Car availability parameter only affects car owners
                    if not agent.has_car and not car_ok:
                        continue  # no redundant runs for non-car-owners
                    
                    for frust in frustrations:
                        total_runs += 1
                        
                        # Configure household car state
                        if agent.household:
                            agent.household.cars_available = 1 if car_ok else 0
                            
                        # Configure memory frustration state
                        if frust > 0:
                            # Build up frustration on a typically preferred mode
                            pref_mode = Mode.CAR if agent.has_car else (Mode.BIKE if agent.has_bike else Mode.BUS)
                            agent.memory.frustration_by_mode[pref_mode] = frust
                        else:
                            agent.memory.frustration_by_mode.clear()
                            
                        try:
                            alts = default_alternatives(agent, distance_km=dist, rain_intensity=rain)
                            chosen_mode = model.choose(agent, alts, stochastic=False)
                            successful_runs += 1
                            
                            dist_lbl = f"{dist:.1f}k"
                            rain_lbl = f"{rain:.1f}"
                            car_lbl = "YES" if car_ok else "NO"
                            frust_lbl = "YES" if frust > 0 else "NO"
                            
                            print(f"{occ.value:22s} | {dist_lbl:5s} | {rain_lbl:4s} | {car_lbl:6s} | {frust_lbl:5s} | {chosen_mode.value:11s}")
                            
                        except Exception as e:
                            print(f"{occ.value:22s} | Error: {str(e)}")
                            
    print("\n======================================================================")
    print("      SMOKE TEST SUMMARY")
    print("======================================================================")
    print(f"Total Sweep Conditions Tested : {total_runs}")
    print(f"Successful Execution Rate     : {successful_runs}/{total_runs} ({successful_runs/total_runs:.1%})")
    print("======================================================================\n")


if __name__ == "__main__":
    main()
