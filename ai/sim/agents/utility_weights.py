from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UtilityWeights:
    """Per-agent (or default) mode-choice utility coefficients. See PROJECT_SPEC §7.2."""

    beta_time: float = -0.08       # per minute
    beta_cost: float = -0.02       # per ₹ (further scaled by income inside the model)
    beta_comfort: float = 0.5
    beta_weather: float = -1.5
    beta_habit: float = 0.4
