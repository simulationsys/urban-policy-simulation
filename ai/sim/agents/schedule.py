from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ActivitySchedule:
    """Stylised daily schedule. Times are minutes since midnight, sim-local."""

    leave_home_min: int = 9 * 60        # 09:00
    leave_home_jitter: int = 30
    work_duration_min: int = 8 * 60     # 8h
    return_jitter: int = 45
    discretionary_evening_prob: float = 0.1

    def return_home_min(self) -> int:
        return self.leave_home_min + self.work_duration_min
