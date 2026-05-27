from __future__ import annotations

import numpy as np

from sim.agents import (
    Agent,
    CommuteOutcome,
    Mode,
    ModeChoiceModel,
)
from sim.agents.mode_choice import ModeAlternative


def make_agent(income: int = 3) -> Agent:
    return Agent(
        id=1,
        home_node=0,
        work_node=1,
        income_bracket=income,
        age=30,
        household_id=1,
        has_bike=True,
    )


def test_available_modes_respects_ownership() -> None:
    a = make_agent()
    modes = a.available_modes()
    assert Mode.BIKE in modes
    assert Mode.CAR not in modes


def test_memory_habit_bonus() -> None:
    a = make_agent()
    for _ in range(3):
        a.memory.record(CommuteOutcome(Mode.METRO, 30, 20, 0.7))
    a.memory.record(CommuteOutcome(Mode.BUS, 40, 15, 0.5))
    assert a.memory.habit_bonus(Mode.METRO) == 0.75
    assert a.memory.habit_bonus(Mode.CAR) == 0.0


def test_mode_choice_prefers_faster_option_deterministic() -> None:
    model = ModeChoiceModel(rng=np.random.default_rng(0))
    a = make_agent()
    alts = [
        ModeAlternative(Mode.BUS, travel_time_min=60, monetary_cost=20, comfort_score=0.4),
        ModeAlternative(Mode.METRO, travel_time_min=25, monetary_cost=25, comfort_score=0.7),
    ]
    choice = model.choose(a, alts, stochastic=False)
    assert choice == Mode.METRO


def test_rain_pushes_agent_off_exposed_modes() -> None:
    model = ModeChoiceModel(rng=np.random.default_rng(0))
    a = make_agent()
    dry = [
        ModeAlternative(Mode.BIKE, 20, 0, 0.6, weather_penalty=0.0),
        ModeAlternative(Mode.METRO, 25, 25, 0.7, weather_penalty=0.0),
    ]
    wet = [
        ModeAlternative(Mode.BIKE, 20, 0, 0.6, weather_penalty=1.0),
        ModeAlternative(Mode.METRO, 25, 25, 0.7, weather_penalty=0.0),
    ]
    assert model.choose(a, dry, stochastic=False) == Mode.BIKE
    assert model.choose(a, wet, stochastic=False) == Mode.METRO
