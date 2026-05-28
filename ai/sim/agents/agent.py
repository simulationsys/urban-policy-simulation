from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from sim.agents.memory import AgentMemory
from sim.agents.modes import Mode
from sim.agents.schedule import ActivitySchedule
from sim.agents.utility_weights import UtilityWeights

NodeID = int


class AgentState(str, Enum):
    AT_HOME = "at_home"
    COMMUTING = "commuting"
    AT_WORK = "at_work"
    RETURNING = "returning"


@dataclass
class Agent:
    """Single simulated citizen. See PROJECT_SPEC §7.1."""

    id: int
    home_node: NodeID
    work_node: NodeID | None
    income_bracket: int  # 1..5
    age: int
    household_id: int
    has_car: bool = False
    has_bike: bool = False
    has_metro_pass: bool = False
    schedule: ActivitySchedule = field(default_factory=ActivitySchedule)
    memory: AgentMemory = field(default_factory=AgentMemory)
    weights: UtilityWeights | None = None  # None → use model default
    current_state: AgentState = AgentState.AT_HOME
    current_mode: Mode | None = None
    current_route: list[NodeID] | None = None

    def available_modes(self) -> list[Mode]:
        modes: list[Mode] = [Mode.WALK, Mode.BUS, Mode.METRO, Mode.AUTO]
        if self.has_bike:
            modes.append(Mode.BIKE)
        if self.has_car:
            modes.append(Mode.CAR)
        return modes
