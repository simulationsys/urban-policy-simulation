from __future__ import annotations

import numpy as np
import pytest

from sim.agents.agent import Agent
from sim.agents.alternatives import default_alternatives
from sim.agents.household import Household
from sim.agents.memory import CommuteOutcome
from sim.agents.mode_choice import ModeAlternative, ModeChoiceModel
from sim.agents.modes import Mode, Occupation
from sim.agents.population import build_population
from sim.agents.schedule import Activity, ActivitySchedule, ActivityType
from sim.agents.utility_weights import UtilityWeights


def test_archetype_utility_weights() -> None:
    """Ensure that default archetype utility weight profiles are loaded correctly."""
    exec_weights = UtilityWeights.for_occupation(Occupation.OFFICE_EXECUTIVE)
    student_weights = UtilityWeights.for_occupation(Occupation.STUDENT)
    
    assert exec_weights.beta_comfort > student_weights.beta_comfort
    assert exec_weights.beta_cost > student_weights.beta_cost  # Executives are less cost-sensitive (cost coeff closer to 0)
    assert student_weights.beta_cost < -0.05


def test_schedule_multi_leg_routing() -> None:
    """Ensure that multi-leg activities can be retrieved as sequential legs."""
    home_node = 100
    work_node = 200
    shop_node = 300
    
    schedule = ActivitySchedule(
        activities=[
            Activity(ActivityType.HOME, home_node, 0, 0),
            Activity(ActivityType.WORK, work_node, 540, 540),
            Activity(ActivityType.SHOPPING, shop_node, 1100, 60),
        ]
    )
    
    legs = schedule.get_legs()
    assert len(legs) == 3
    
    # Leg 1: Home -> Work
    assert legs[0][0].activity_type == ActivityType.HOME
    assert legs[0][1].activity_type == ActivityType.WORK
    
    # Leg 2: Work -> Shopping
    assert legs[1][0].activity_type == ActivityType.WORK
    assert legs[1][1].activity_type == ActivityType.SHOPPING
    
    # Leg 3: Shopping -> Home (auto-loopback)
    assert legs[2][0].activity_type == ActivityType.SHOPPING
    assert legs[2][1].activity_type == ActivityType.HOME


def test_memory_schedule_and_mode_adaptation() -> None:
    """Ensure schedule shifts earlier on consecutive delays, and frustration causes mode switch."""
    home = 10
    work = 20
    
    agent = Agent(
        id=99,
        home_node=home,
        work_node=work,
        income_bracket=3,
        age=30,
        household_id=1,
        occupation=Occupation.OFFICE_EXECUTIVE,
        weights=UtilityWeights(beta_cost=-0.01, beta_time=-0.1),
        schedule=ActivitySchedule(
            activities=[
                Activity(ActivityType.HOME, home, 0, 0),
                Activity(ActivityType.WORK, work, 540, 540),
            ]
        ),
    )
    
    agent.current_mode = Mode.CAR
    
    # Record 3 baseline outcomes (avg travel time ~25 mins)
    for _ in range(3):
        agent.memory.record(CommuteOutcome(Mode.CAR, 25.0, 20.0, 0.8))
        
    # Record 3 severe delays (travel time 45 mins)
    for _ in range(3):
        agent.memory.record(CommuteOutcome(Mode.CAR, 45.0, 20.0, 0.8))
        
    # 1. Schedule Adaptation
    agent.adapt_behavior()
    # The departure activity (index 1) should shift earlier by 15 mins (from 540 to 525)
    assert agent.schedule.activities[1].start_time_min == 525
    
    # 2. Mode Frustration & Choice Override
    # CAR is fast (20 mins) but highly frustrated. METRO is slower (30 mins) but clean.
    model = ModeChoiceModel(rng=np.random.default_rng(0))
    alts = [
        ModeAlternative(Mode.CAR, travel_time_min=20.0, monetary_cost=20.0, comfort_score=0.8),
        ModeAlternative(Mode.METRO, travel_time_min=30.0, monetary_cost=10.0, comfort_score=0.6),
    ]
    
    # CAR frustration should be 3.0 (maximum)
    assert agent.memory.get_frustration(Mode.CAR) == 3.0
    
    # Should choose METRO because CAR has severe frustration penalty
    choice = model.choose(agent, alts, stochastic=False)
    assert choice == Mode.METRO


def test_household_car_sharing() -> None:
    """Ensure household car mutual exclusion (only one member can drive it)."""
    hh = Household(id=999, has_car=True, cars_owned=1, cars_available=1)
    
    agent_a = Agent(
        id=1,
        home_node=10,
        work_node=20,
        income_bracket=4,
        age=30,
        household_id=999,
        has_car=True,
        household=hh,
    )
    
    agent_b = Agent(
        id=2,
        home_node=10,
        work_node=30,
        income_bracket=4,
        age=28,
        household_id=999,
        has_car=True,
        household=hh,
    )
    
    hh.member_ids = [1, 2]
    
    # Both initially have CAR in their available modes
    assert Mode.CAR in agent_a.available_modes()
    assert Mode.CAR in agent_b.available_modes()
    
    # Agent A claims the car
    success = hh.request_car()
    assert success is True
    assert hh.cars_available == 0
    
    # Now Agent B should NOT have Mode.CAR in available modes
    assert Mode.CAR not in agent_b.available_modes()
    
    # Agent A releases the car
    hh.release_car()
    assert hh.cars_available == 1
    assert Mode.CAR in agent_b.available_modes()


def test_joint_escort_run() -> None:
    """Ensure parent-child linking and school escort leg insertion works in population builder."""
    rng = np.random.default_rng(42)
    # Build a small population. Setting seed guarantees specific sizes.
    agents = build_population(15, rng=rng)
    
    # Find a parent linked to a child
    parents = [a for a in agents if len(a.child_ids) > 0]
    if parents:
        parent = parents[0]
        # Parent schedule should contain an ESCORTING leg before work!
        act_types = [act.activity_type for act in parent.schedule.activities]
        assert ActivityType.ESCORTING in act_types
        
        # Escorting node should match the child's school node
        child = next(c for c in agents if c.id == parent.child_ids[0])
        school_node = child.activity_locations[ActivityType.EDUCATION]
        escort_act = next(act for act in parent.schedule.activities if act.activity_type == ActivityType.ESCORTING)
        assert escort_act.location_node == school_node
