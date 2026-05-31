from dataclasses import dataclass, field
from enum import Enum

NodeID = int


class ActivityType(str, Enum):
    HOME = "home"
    WORK = "work"
    EDUCATION = "education"
    SHOPPING = "shopping"
    RECREATION = "recreation"
    GIG_WORK = "gig_work"
    ESCORTING = "escorting"


@dataclass
class Activity:
    activity_type: ActivityType
    location_node: NodeID
    start_time_min: int  # minutes since midnight
    duration_min: int  # minutes


@dataclass
class ActivitySchedule:
    """Stylised daily schedule. Supports multiple activities (multi-leg tours)."""

    activities: list[Activity] = field(default_factory=list)
    leave_home_min: int = 9 * 60        # 09:00
    leave_home_jitter: int = 30
    work_duration_min: int = 8 * 60     # 8h
    return_jitter: int = 45
    discretionary_evening_prob: float = 0.1

    def get_legs(self) -> list[tuple[Activity, Activity]]:
        """Returns a list of legs as (origin_activity, destination_activity) pairs.

        Assumes the first activity is home, and it loops back to home if not ended at home.
        """
        if not self.activities:
            return []
        legs = []
        for i in range(len(self.activities) - 1):
            legs.append((self.activities[i], self.activities[i + 1]))
        if self.activities[-1].activity_type != ActivityType.HOME:
            legs.append((self.activities[-1], self.activities[0]))
        return legs

    def return_home_min(self) -> int:
        """Helper to maintain backwards compatibility or retrieve final arrival target."""
        if not self.activities:
            return self.leave_home_min + self.work_duration_min

        work_act = next((a for a in self.activities if a.activity_type == ActivityType.WORK), None)
        if work_act:
            return work_act.start_time_min + work_act.duration_min

        last_non_home = [a for a in self.activities if a.activity_type != ActivityType.HOME]
        if last_non_home:
            return last_non_home[-1].start_time_min + last_non_home[-1].duration_min
        return self.leave_home_min + self.work_duration_min
