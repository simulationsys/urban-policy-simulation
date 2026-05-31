from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sim.agents.modes import Occupation


@dataclass
class UtilityWeights:
    """Per-agent (or default) mode-choice utility coefficients. See PROJECT_SPEC §7.2."""

    beta_time: float = -0.08       # per minute
    beta_cost: float = -0.02       # per ₹ (further scaled by income inside the model)
    beta_comfort: float = 0.5
    beta_weather: float = -1.5
    beta_habit: float = 0.4

    @staticmethod
    def for_occupation(occupation: Occupation) -> UtilityWeights:
        from sim.agents.modes import Occupation

        if occupation == Occupation.OFFICE_EXECUTIVE:
            return UtilityWeights(
                beta_time=-0.15,
                beta_cost=-0.002,
                beta_comfort=1.8,
                beta_weather=-0.4,
                beta_habit=0.4,
            )
        elif occupation == Occupation.STUDENT:
            return UtilityWeights(
                beta_time=-0.04,
                beta_cost=-0.08,
                beta_comfort=0.1,
                beta_weather=-1.5,
                beta_habit=0.3,
            )
        elif occupation == Occupation.BLUE_COLLAR_WORKER:
            return UtilityWeights(
                beta_time=-0.10,
                beta_cost=-0.05,
                beta_comfort=0.2,
                beta_weather=-1.2,
                beta_habit=0.5,
            )
        elif occupation == Occupation.GIG_WORKER:
            return UtilityWeights(
                beta_time=-0.18,
                beta_cost=-0.06,
                beta_comfort=0.1,
                beta_weather=-1.0,
                beta_habit=0.2,
            )
        elif occupation == Occupation.RETIRED_CITIZEN:
            return UtilityWeights(
                beta_time=-0.03,
                beta_cost=-0.03,
                beta_comfort=1.2,
                beta_weather=-2.5,
                beta_habit=0.6,
            )
        return UtilityWeights()
