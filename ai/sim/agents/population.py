"""Synthetic population factory.

Until SUB-04 publishes a real synthetic population, this builds plausible
heterogeneous agents from simple distributions. Replace the sampling block
with the SUB-04 DataFrame loader when it's ready — keep the Agent shape stable.

The role doc calls heterogeneity "the cheapest realism": every agent gets a
slightly different set of utility weights and demographic profile so the
aggregate behaviour is not a single point.
"""

from __future__ import annotations

import numpy as np

from sim.agents.agent import Agent
from sim.agents.schedule import ActivitySchedule
from sim.agents.utility_weights import UtilityWeights

# Vehicle-ownership probability by income bracket (1=lowest .. 5=highest).
# Loose proxy for Indian urban context; calibrate later against survey data.
P_CAR_BY_INCOME = {1: 0.02, 2: 0.08, 3: 0.20, 4: 0.45, 5: 0.70}
P_BIKE_BY_INCOME = {1: 0.10, 2: 0.30, 3: 0.50, 4: 0.55, 5: 0.45}
P_METRO_PASS = 0.25


def _sample_weights(income: int, rng: np.random.Generator) -> UtilityWeights:
    """Per-agent weights = base weights + Gaussian jitter, with income-aware tweaks."""
    base = UtilityWeights()
    # Higher income → less sensitive to cost in absolute terms (income_scale in
    # ModeChoiceModel already does some of this; jitter keeps individual variation).
    jitter = lambda mu, sd: float(rng.normal(mu, sd))  # noqa: E731
    return UtilityWeights(
        beta_time=jitter(base.beta_time, 0.015),
        beta_cost=jitter(base.beta_cost, 0.005),
        beta_comfort=jitter(base.beta_comfort, 0.1),
        beta_weather=jitter(base.beta_weather, 0.3),
        beta_habit=jitter(base.beta_habit, 0.1),
    )


def _sample_schedule(rng: np.random.Generator) -> ActivitySchedule:
    leave = int(rng.normal(9 * 60, 45))  # ~09:00 ±45min
    work = int(rng.normal(8 * 60, 30))   # ~8h ±30min
    return ActivitySchedule(
        leave_home_min=max(5 * 60, min(12 * 60, leave)),
        work_duration_min=max(5 * 60, min(11 * 60, work)),
    )


def build_population(
    n: int,
    *,
    n_nodes: int = 1000,
    rng: np.random.Generator | None = None,
) -> list[Agent]:
    """Build `n` heterogeneous agents with random home/work nodes from [0, n_nodes)."""
    rng = rng or np.random.default_rng()
    # Income bracket distribution — skewed toward middle (1..5).
    income_p = np.array([0.20, 0.30, 0.25, 0.15, 0.10])
    incomes = rng.choice(np.arange(1, 6), size=n, p=income_p)
    ages = rng.integers(18, 70, size=n)
    home_nodes = rng.integers(0, n_nodes, size=n)
    work_nodes = rng.integers(0, n_nodes, size=n)
    household_ids = rng.integers(0, max(1, n // 3), size=n)

    agents: list[Agent] = []
    for i in range(n):
        income = int(incomes[i])
        has_car = bool(rng.random() < P_CAR_BY_INCOME[income])
        has_bike = bool(rng.random() < P_BIKE_BY_INCOME[income])
        agents.append(
            Agent(
                id=i,
                home_node=int(home_nodes[i]),
                work_node=int(work_nodes[i]),
                income_bracket=income,
                age=int(ages[i]),
                household_id=int(household_ids[i]),
                has_car=has_car,
                has_bike=has_bike,
                has_metro_pass=bool(rng.random() < P_METRO_PASS),
                schedule=_sample_schedule(rng),
                weights=_sample_weights(income, rng),
            )
        )
    return agents
