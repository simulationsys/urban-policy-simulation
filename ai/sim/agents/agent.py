from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from sim.agents.household import Household
from sim.agents.memory import AgentMemory
from sim.agents.modes import Mode, Occupation
from sim.agents.schedule import ActivitySchedule, ActivityType
from sim.agents.utility_weights import UtilityWeights

NodeID = int


class AgentState(str, Enum):
    AT_HOME = "at_home"
    COMMUTING = "commuting"
    AT_WORK = "at_work"
    RETURNING = "returning"


@dataclass
class Agent:
    """Single simulated citizen. See PROJECT_SPEC §7.1 and expanded plan."""

    id: int
    home_node: NodeID
    work_node: NodeID | None
    income_bracket: int  # 1..5
    age: int
    household_id: int
    occupation: Occupation = Occupation.BLUE_COLLAR_WORKER
    has_car: bool = False
    has_bike: bool = False
    has_metro_pass: bool = False
    schedule: ActivitySchedule = field(default_factory=ActivitySchedule)
    memory: AgentMemory = field(default_factory=AgentMemory)
    weights: UtilityWeights | None = None  # None → use model default
    current_state: AgentState = AgentState.AT_HOME
    current_mode: Mode | None = None
    current_route: list[NodeID] | None = None
    household: Household | None = None
    
    # Advanced extensions from plan
    activity_locations: dict[ActivityType, NodeID] = field(default_factory=dict)
    parent_id: int | None = None
    child_ids: list[int] = field(default_factory=list)

    def available_modes(self) -> list[Mode]:
        modes: list[Mode] = [Mode.WALK, Mode.BUS, Mode.METRO, Mode.AUTO]
        if self.has_bike:
            modes.append(Mode.BIKE)
        if self.has_car:
            if self.household is not None:
                if self.household.cars_available > 0:
                    modes.append(Mode.CAR)
            else:
                modes.append(Mode.CAR)
        return modes

    def adapt_behavior(self) -> None:
        """Called daily to adapt schedule departure times based on commute performance.

        If the last three commutes on their active mode were 15% slower than their rolling
        average for that mode, they shift departure time 15 minutes earlier.
        """
        if self.current_mode:
            buf = self.memory.by_mode.get(self.current_mode)
            if buf and len(buf) >= 3:
                last_three = list(buf)[-3:]
                avg = sum(o.travel_time_min for o in buf) / len(buf)
                if all(o.travel_time_min > avg * 1.15 for o in last_three):
                     # Shift leave time earlier by 15 mins (up to a limit of 06:00 AM)
                     if self.schedule.activities:
                         # The second activity in schedule is where they leave HOME
                         if len(self.schedule.activities) > 1:
                             second_act = self.schedule.activities[1]
                             old_start = second_act.start_time_min
                             new_start = max(6 * 60, old_start - 15)
                             second_act.start_time_min = new_start
                             self.schedule.leave_home_min = new_start
                     else:
                         self.schedule.leave_home_min = max(6 * 60, self.schedule.leave_home_min - 15)
