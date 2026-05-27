"""Multinomial-logit mode choice. See PROJECT_SPEC §7.2.

U(mode) = β_time*time + β_cost*cost + β_comfort*comfort
          + β_weather*weather_penalty + β_habit*habit_bonus + ε
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from sim.agents.agent import Agent
from sim.agents.modes import Mode


@dataclass
class UtilityWeights:
    beta_time: float = -0.08       # per minute
    beta_cost: float = -0.02       # per ₹ (scaled by income inside model)
    beta_comfort: float = 0.5
    beta_weather: float = -1.5
    beta_habit: float = 0.4


@dataclass
class ModeAlternative:
    mode: Mode
    travel_time_min: float
    monetary_cost: float
    comfort_score: float           # 0..1
    weather_penalty: float = 0.0   # 0..1; higher when rain + exposed mode


class ModeChoiceModel:
    def __init__(self, weights: UtilityWeights | None = None, rng: np.random.Generator | None = None):
        self.w = weights or UtilityWeights()
        self.rng = rng or np.random.default_rng()

    def utility(self, agent: Agent, alt: ModeAlternative) -> float:
        w = self.w
        # Lower-income agents weight cost more heavily.
        cost_scale = (6 - agent.income_bracket) / 3.0
        habit = agent.memory.habit_bonus(alt.mode)
        return (
            w.beta_time * alt.travel_time_min
            + w.beta_cost * cost_scale * alt.monetary_cost
            + w.beta_comfort * alt.comfort_score
            + w.beta_weather * alt.weather_penalty
            + w.beta_habit * habit
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
