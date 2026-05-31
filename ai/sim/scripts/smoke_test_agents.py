"""Consolidated Comprehensive Agent Smoke Test.

Runs sweeps across two major axes:
- Axis 1: Core environmental conditions (Trip distances, rain levels, car sharing availability, memory frustration).
- Axis 2: Policy interventions and income brackets (Standard fare, fuel pricing hikes, transit subsidies, transit overcrowding).

Usage: python -m sim.scripts.smoke_test_agents
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
    hh = Household(id=700, has_car=True, cars_owned=1, cars_available=1)
    
    agents = {
        Occupation.OFFICE_EXECUTIVE: Agent(
            id=1,
            home_node=10,
            work_node=20,
            income_bracket=5,
            age=40,
            household_id=700,
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
            household_id=701,
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
            household_id=702,
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
            household_id=703,
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
            household_id=704,
            occupation=Occupation.RETIRED_CITIZEN,
            weights=UtilityWeights.for_occupation(Occupation.RETIRED_CITIZEN),
        ),
    }
    
    hh.member_ids = [1]
    return agents


def run_condition_sweep(model: ModeChoiceModel, agents: dict[Occupation, Agent]) -> tuple[int, int]:
    """Test agents under varying distances, rains, car sharing, and frustration states."""
    distances = [1.5, 7.5, 18.0]
    rains = [0.0, 0.4, 1.0]
    car_shares = [True, False]
    frustrations = [0.0, 3.0]
    
    print("\n" + "=" * 72)
    print("  SWEEP AXIS 1: CORE ENVIRONMENTAL & BEHAVIORAL CONDITIONS")
    print("=" * 72)
    print(f"{'ARCHETYPE':22s} | {'DIST':5s} | {'RAIN':4s} | {'CAR_OK':6s} | {'FRUST':5s} | {'CHOSEN MODE':11s}")
    print("-" * 72)
    
    total = 0
    success = 0
    
    for occ, agent in agents.items():
        for dist in distances:
            for rain in rains:
                for car_ok in car_shares:
                    if not agent.has_car and not car_ok:
                        continue
                    
                    for frust in frustrations:
                        total += 1
                        if agent.household:
                            agent.household.cars_available = 1 if car_ok else 0
                            
                        if frust > 0:
                            pref_mode = Mode.CAR if agent.has_car else (Mode.BIKE if agent.has_bike else Mode.BUS)
                            agent.memory.frustration_by_mode[pref_mode] = frust
                        else:
                            agent.memory.frustration_by_mode.clear()
                            
                        try:
                            alts = default_alternatives(agent, distance_km=dist, rain_intensity=rain)
                            chosen_mode = model.choose(agent, alts, stochastic=False)
                            success += 1
                            
                            dist_lbl = f"{dist:.1f}k"
                            rain_lbl = f"{rain:.1f}"
                            car_lbl = "YES" if car_ok else "NO"
                            frust_lbl = "YES" if frust > 0 else "NO"
                            print(f"{occ.value:22s} | {dist_lbl:5s} | {rain_lbl:4s} | {car_lbl:6s} | {frust_lbl:5s} | {chosen_mode.value:11s}")
                        except Exception as e:
                            print(f"{occ.value:22s} | Error: {str(e)}")
                            
    return total, success


def run_policy_sweep(model: ModeChoiceModel, agents: dict[Occupation, Agent]) -> tuple[int, int]:
    """Test agents under policy interventions and income level swings."""
    policies = ["baseline", "fuel_surge", "transit_subsidy", "heavy_crowding"]
    income_brackets = [1, 3, 5]
    
    print("\n" + "=" * 72)
    print("  SWEEP AXIS 2: POLICY INTERVENTIONS & INCOME BRACKETS")
    print("=" * 72)
    print(f"{'ARCHETYPE':22s} | {'INCOME':6s} | {'POLICY SCENARIO':16s} | {'CHOSEN MODE':11s}")
    print("-" * 72)
    
    total = 0
    success = 0
    
    for occ, agent in agents.items():
        dist = 2.5 if occ == Occupation.RETIRED_CITIZEN else 10.0
        
        for income in income_brackets:
            agent.income_bracket = income
            
            for policy in policies:
                total += 1
                try:
                    alts = default_alternatives(agent, distance_km=dist, rain_intensity=0.0)
                    for alt in alts:
                        if policy == "fuel_surge":
                            if alt.mode in {Mode.CAR, Mode.AUTO}:
                                alt.monetary_cost *= 1.8
                        elif policy == "transit_subsidy":
                            if alt.mode in {Mode.BUS, Mode.METRO}:
                                alt.monetary_cost *= 0.5
                        elif policy == "heavy_crowding":
                            if alt.mode == Mode.METRO:
                                alt.comfort_score = 0.20
                            elif alt.mode == Mode.BUS:
                                alt.comfort_score = 0.05
                                
                    chosen_mode = model.choose(agent, alts, stochastic=False)
                    success += 1
                    
                    policy_lbl = policy.upper()
                    print(f"{occ.value:22s} | Bracket {income} | {policy_lbl:16s} | {chosen_mode.value:11s}")
                except Exception as e:
                    print(f"{occ.value:22s} | Bracket {income} | Error: {str(e)}")
                    
    return total, success


def main() -> None:
    rng = np.random.default_rng(42)
    model = ModeChoiceModel(rng=rng)
    
    print("======================================================================")
    print("   CONSOLIDATED COMPREHENSIVE SMOKE TEST - URBAN POLICY SIMULATION    ")
    print("======================================================================")
    
    agents = build_test_agents()
    
    # Run environmental & behavioral sweeps
    cond_total, cond_success = run_condition_sweep(model, agents)
    
    # Run policy & income sweeps
    policy_total, policy_success = run_policy_sweep(model, agents)
    
    total_runs = cond_total + policy_total
    successful_runs = cond_success + policy_success
    
    print("\n" + "=" * 72)
    print("      CONSOLIDATED SMOKE TEST SUMMARY")
    print("=" * 72)
    print(f"Total Parameter Sweep Runs    : {total_runs}")
    print(f"Successful Execution Rate     : {successful_runs}/{total_runs} ({successful_runs/total_runs:.1%})")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()
