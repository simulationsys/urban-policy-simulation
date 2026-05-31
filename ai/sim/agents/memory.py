from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from sim.agents.modes import Mode


@dataclass
class CommuteOutcome:
    mode: Mode
    travel_time_min: float
    monetary_cost: float
    comfort_score: float  # 0..1; higher = more comfortable


@dataclass
class AgentMemory:
    """Per-agent rolling memory of recent commute outcomes per mode."""

    window: int = 10
    by_mode: dict[Mode, deque[CommuteOutcome]] = field(default_factory=dict)
    frustration_by_mode: dict[Mode, float] = field(default_factory=dict)

    def record(self, outcome: CommuteOutcome) -> None:
        buf = self.by_mode.setdefault(outcome.mode, deque(maxlen=self.window))
        
        # Calculate moving average before adding the new outcome
        old_avg = None
        if len(buf) >= 2:
            old_avg = sum(o.travel_time_min for o in buf) / len(buf)
            
        buf.append(outcome)

        # Update frustration
        if old_avg is not None and outcome.travel_time_min > old_avg * 1.25:
            # 25% or more above average commute time -> increase frustration
            self.frustration_by_mode[outcome.mode] = min(
                3.0, self.frustration_by_mode.get(outcome.mode, 0.0) + 1.0
            )
        else:
            # Normal or good commute -> cool down frustration by 0.5 (daily cooling)
            self.frustration_by_mode[outcome.mode] = max(
                0.0, self.frustration_by_mode.get(outcome.mode, 0.0) - 0.5
            )

    def avg_time(self, mode: Mode) -> float | None:
        buf = self.by_mode.get(mode)
        if not buf:
            return None
        return sum(o.travel_time_min for o in buf) / len(buf)

    def get_frustration(self, mode: Mode) -> float:
        return self.frustration_by_mode.get(mode, 0.0)

    def habit_bonus(self, mode: Mode) -> float:
        """Fraction of recent trips taken on this mode across all modes seen."""
        total = sum(len(b) for b in self.by_mode.values())
        if total == 0:
            return 0.0
        return len(self.by_mode.get(mode, ())) / total
