"""Two hand-built agents, side by side.

Priya (low income, no car, has bike) and Rohan (high income, car owner) live
in the same city. Same trip distance, same weather — different decisions.
This is a tiny illustration of why heterogeneity matters: aggregate mode
share is the sum of agents like these making different calls.

Usage:  python -m sim.scripts.demo_two_agents
"""

from __future__ import annotations

import numpy as np

from sim.agents.agent import Agent
from sim.agents.alternatives import default_alternatives
from sim.agents.memory import CommuteOutcome
from sim.agents.mode_choice import ModeChoiceModel
from sim.agents.modes import Mode
from sim.agents.schedule import ActivitySchedule
from sim.agents.utility_weights import UtilityWeights


def make_priya() -> Agent:
    return Agent(
        id=1,
        home_node=10,
        work_node=42,
        income_bracket=1,           # low income
        age=28,
        household_id=100,
        has_car=False,
        has_bike=True,
        has_metro_pass=True,
        schedule=ActivitySchedule(leave_home_min=8 * 60 + 15),
        # Cost-sensitive, strongly rain-averse (no rain gear).
        weights=UtilityWeights(beta_cost=-0.08, beta_weather=-2.8),
    )


def make_rohan() -> Agent:
    return Agent(
        id=2,
        home_node=11,
        work_node=43,
        income_bracket=5,           # high income
        age=42,
        household_id=200,
        has_car=True,
        has_bike=False,
        has_metro_pass=False,
        schedule=ActivitySchedule(leave_home_min=9 * 60 + 30),
        # Effectively cost-blind, strongly comfort-driven (drives a car).
        weights=UtilityWeights(beta_time=-0.15, beta_cost=-0.002, beta_comfort=1.8, beta_weather=-0.4),
    )


def report(agent: Agent, label: str, model: ModeChoiceModel) -> None:
    print(f"\n--- {label} (id={agent.id}, income={agent.income_bracket}, "
          f"car={agent.has_car}, bike={agent.has_bike}) ---")
    print(f"   schedule: leave {agent.schedule.leave_home_min // 60:02d}:"
          f"{agent.schedule.leave_home_min % 60:02d}, "
          f"work {agent.schedule.work_duration_min / 60:.1f}h")
    print(f"   available modes: {[m.value for m in agent.available_modes()]}")

    for rain_label, rain in [("dry", 0.0), ("heavy rain", 1.0)]:
        alts = default_alternatives(agent, distance_km=8.0, rain_intensity=rain)
        choice = model.choose(agent, alts, stochastic=False)
        utilities = {a.mode.value: round(model.utility(agent, a), 2) for a in alts}
        print(f"   [{rain_label}]  picks {choice.value:6s}  U={utilities}")


def main() -> None:
    rng = np.random.default_rng(0)
    model = ModeChoiceModel(rng=rng)
    priya = make_priya()
    rohan = make_rohan()

    report(priya, "Priya", model)
    report(rohan, "Rohan", model)

    # Show memory adapting: give Priya three bad bus commutes and re-decide.
    print("\nSimulating: Priya has 3 bad bus commutes in a row...")
    for _ in range(3):
        priya.memory.record(CommuteOutcome(Mode.BUS, travel_time_min=60, monetary_cost=12, comfort_score=0.2))
    alts = default_alternatives(priya, distance_km=8.0, rain_intensity=0.0)
    choice = model.choose(priya, alts, stochastic=False)
    print(f"   after experience, Priya picks: {choice.value}")


if __name__ == "__main__":
    main()
