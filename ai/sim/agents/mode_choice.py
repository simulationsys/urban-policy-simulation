"""Multinomial-logit mode choice. See PROJECT_SPEC §7.2.

U(mode) = β_time*time + β_cost*cost + β_comfort*comfort
          + β_weather*weather_penalty + β_habit*habit_bonus + ε
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from sim.agents.agent import Agent
from sim.agents.modes import Mode
from sim.agents.utility_weights import UtilityWeights


@dataclass
class ModeAlternative:
    mode: Mode
    travel_time_min: float
    monetary_cost: float
    comfort_score: float           # 0..1
    weather_penalty: float = 0.0   # 0..1; higher when rain + exposed mode


class ModeChoiceModel:

    # Non-linear income-stratified cost sensitivity (PRD §4, SUB-02, task 2.1).
    # Fuel shocks hit low-income auto/car users much harder than high-income.
    _INCOME_COST_SCALE: dict[int, float] = {
        1: 3.0,   # Lowest income — extremely cost-sensitive
        2: 1.8,   # Low-medium
        3: 0.9,   # Medium
        4: 0.3,   # Medium-high
        5: 0.05,  # Highest income — virtually cost-insensitive
    }

    def __init__(self, weights: UtilityWeights | None = None, rng: np.random.Generator | None = None):
        self.w = weights or UtilityWeights()
        self.rng = rng or np.random.default_rng()

    def utility(self, agent: Agent, alt: ModeAlternative) -> float:
        w = agent.weights or self.w
        # Non-linear income-stratified cost sensitivity (SUB-02, task 2.1).
        # Low-income agents are dramatically more sensitive to cost changes
        # (e.g. fuel shock), while high-income agents are nearly insensitive.
        cost_scale = self._INCOME_COST_SCALE.get(agent.income_bracket, 0.9)
        habit = agent.memory.habit_bonus(alt.mode)
        frustration = agent.memory.get_frustration(alt.mode)
        return (
            w.beta_time * alt.travel_time_min
            + w.beta_cost * cost_scale * alt.monetary_cost
            + w.beta_comfort * alt.comfort_score
            + w.beta_weather * alt.weather_penalty
            + w.beta_habit * habit
            - frustration * 0.8
        )

    def choose(self, agent: Agent, alts: list[ModeAlternative], stochastic: bool = True) -> Mode:
        if not alts:
            raise ValueError("No mode alternatives provided")
        utilities = np.array([self.utility(agent, a) for a in alts], dtype=float)
        if stochastic:
            # Gumbel noise → softmax-equivalent sampling (MNL).
            gumbel = self.rng.gumbel(size=utilities.shape)
            idx = int(np.argmax(utilities + gumbel))
        else:
            idx = int(np.argmax(utilities))
        return alts[idx].mode
