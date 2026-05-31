"""Policy and Income Intervention Sweep Test.

Tests all five occupational archetypes under policy and income swings:
- Policy 1: Standard Pricing vs. Fuel Surcharge/Cab Surge (1.8x CAR/AUTO cost)
- Policy 2: Standard Fare vs. Transit Subsidy (0.5x BUS/METRO cost)
- Policy 3: Comfortable Transit vs. Heavy Peak Crowding (Transit comfort sashed to 0.15)
- Income Bracket Swings: Income 1 (highly cost-sensitive) vs. Income 5 (highly cost-blind)

Usage: python -m sim.scripts.smoke_test_policies
"""

from __future__ import annotations

import numpy as np

from sim.agents.agent import Agent
from sim.agents.alternatives import default_alternatives
from sim.agents.memory import CommuteOutcome
from sim.agents.mode_choice import ModeChoiceModel
from sim.agents.modes import Mode, Occupation
from sim.agents.schedule import Activity, ActivitySchedule, ActivityType
from sim.agents.utility_weights import UtilityWeights


def build_base_agents() -> dict[Occupation, Agent]:
    """Build fresh baseline agents."""
    return {
        Occupation.OFFICE_EXECUTIVE: Agent(
            id=1,
            home_node=10,
            work_node=20,
            income_bracket=4,  # default mid-high
            age=40,
            household_id=600,
            occupation=Occupation.OFFICE_EXECUTIVE,
            has_car=True,
            weights=UtilityWeights.for_occupation(Occupation.OFFICE_EXECUTIVE),
        ),
        Occupation.STUDENT: Agent(
            id=2,
            home_node=11,
            work_node=None,
            income_bracket=1,  # default low
            age=20,
            household_id=601,
            occupation=Occupation.STUDENT,
            has_bike=True,
            weights=UtilityWeights.for_occupation(Occupation.STUDENT),
        ),
        Occupation.BLUE_COLLAR_WORKER: Agent(
            id=3,
            home_node=12,
            work_node=22,
            income_bracket=2,
            age=32,
            household_id=602,
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
            household_id=603,
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
            household_id=604,
            occupation=Occupation.RETIRED_CITIZEN,
            weights=UtilityWeights.for_occupation(Occupation.RETIRED_CITIZEN),
        ),
    }


def main() -> None:
    rng = np.random.default_rng(100)
    model = ModeChoiceModel(rng=rng)
    
    # We will test a fixed medium distance of 10.0km for workers and gig workers, 2.5km for walks/others
    print("======================================================================")
    print("      POLICY INTERVENTION & INCOME SWEEP SMOKE TEST                   ")
    print("======================================================================\n")
    
    policies = ["baseline", "fuel_surge", "transit_subsidy", "heavy_crowding"]
    income_brackets = [1, 3, 5]
    
    print(f"{'ARCHETYPE':22s} | {'INCOME':6s} | {'POLICY SCENARIO':16s} | {'CHOSEN MODE':11s}")
    print("-" * 65)
    
    total_runs = 0
    successful_runs = 0
    
    agents = build_base_agents()
    
    for occ, agent in agents.items():
        dist = 2.5 if occ == Occupation.RETIRED_CITIZEN else 10.0
        
        for income in income_brackets:
            # Update agent income bracket dynamically
            agent.income_bracket = income
            
            for policy in policies:
                total_runs += 1
                
                try:
                    # Generate base mode alternatives
                    alts = default_alternatives(agent, distance_km=dist, rain_intensity=0.0)
                    
                    # Apply policy modifications on alternatives dynamically
                    for alt in alts:
                        if policy == "fuel_surge":
                            if alt.mode in {Mode.CAR, Mode.AUTO}:
                                alt.monetary_cost *= 1.8  # fuel surcharge/cab fare spike
                                
                        elif policy == "transit_subsidy":
                            if alt.mode in {Mode.BUS, Mode.METRO}:
                                alt.monetary_cost *= 0.5  # fare slashed by 50%
                                
                        elif policy == "heavy_crowding":
                            if alt.mode == Mode.METRO:
                                alt.comfort_score = 0.20  # Metro packed to capacity
                            elif alt.mode == Mode.BUS:
                                alt.comfort_score = 0.05  # Bus overcrowded
                                
                    # Select the preferred mode
                    chosen_mode = model.choose(agent, alts, stochastic=False)
                    successful_runs += 1
                    
                    policy_lbl = policy.upper()
                    print(f"{occ.value:22s} | Bracket {income} | {policy_lbl:16s} | {chosen_mode.value:11s}")
                    
                except Exception as e:
                    print(f"{occ.value:22s} | Bracket {income} | Error: {str(e)}")
                    
    print("\n======================================================================")
    print("      POLICY SWEEP SUMMARY")
    print("======================================================================")
    print(f"Total Policy Combinations Tested : {total_runs}")
    print(f"Successful Execution Rate        : {successful_runs}/{total_runs} ({successful_runs/total_runs:.1%})")
    print("======================================================================\n")


if __name__ == "__main__":
    main()
