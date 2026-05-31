"""Synthetic population factory.

Builds highly realistic heterogeneous agents grouped into households,
with distinct occupational archetypes, multi-leg schedules, car sharing,
and parent-child escort relationships.
"""

from __future__ import annotations

import numpy as np

from sim.agents.agent import Agent
from sim.agents.household import Household
from sim.agents.modes import Occupation
from sim.agents.schedule import Activity, ActivitySchedule, ActivityType
from sim.agents.utility_weights import UtilityWeights

# Vehicle-ownership probability by income bracket (1=lowest .. 5=highest).
P_CAR_BY_INCOME = {1: 0.02, 2: 0.08, 3: 0.20, 4: 0.45, 5: 0.70}
P_BIKE_BY_INCOME = {1: 0.10, 2: 0.30, 3: 0.50, 4: 0.55, 5: 0.45}
P_METRO_PASS = 0.25


def _sample_weights(occupation: Occupation, rng: np.random.Generator) -> UtilityWeights:
    """Per-agent weights = base archetype weights + Gaussian jitter."""
    base = UtilityWeights.for_occupation(occupation)
    jitter = lambda mu, sd: float(rng.normal(mu, sd))  # noqa: E731
    return UtilityWeights(
        beta_time=jitter(base.beta_time, 0.015),
        beta_cost=jitter(base.beta_cost, 0.005),
        beta_comfort=jitter(base.beta_comfort, 0.1),
        beta_weather=jitter(base.beta_weather, 0.3),
        beta_habit=jitter(base.beta_habit, 0.1),
    )


def build_population(
    n: int,
    *,
    n_nodes: int = 1000,
    rng: np.random.Generator | None = None,
) -> list[Agent]:
    """Build `n` heterogeneous agents grouped into households with detailed archetypes."""
    rng = rng or np.random.default_rng()
    
    # 1. Generate household size distribution
    # reflecting typical sizes in Indian metropolitan areas
    hh_sizes: list[int] = []
    while sum(hh_sizes) < n:
        hh_sizes.append(int(rng.choice([1, 2, 3, 4, 5], p=[0.15, 0.25, 0.25, 0.20, 0.15])))
    
    if sum(hh_sizes) > n:
        hh_sizes[-1] -= (sum(hh_sizes) - n)
        if hh_sizes[-1] <= 0:
            hh_sizes.pop()

    agents: list[Agent] = []
    agent_id = 0
    hh_id = 0

    for size in hh_sizes:
        # Sample household income bracket (1..5)
        hh_income = int(rng.choice(np.arange(1, 6), p=[0.20, 0.30, 0.25, 0.15, 0.10]))
        
        # Decide car capacity for household
        cars_owned = 0
        if hh_income == 5:
            cars_owned = int(rng.choice([0, 1, 2], p=[0.20, 0.60, 0.20]))
        elif hh_income == 4:
            cars_owned = int(rng.choice([0, 1], p=[0.50, 0.50]))
        elif hh_income == 3:
            cars_owned = int(rng.choice([0, 1], p=[0.80, 0.20]))
        elif hh_income == 2:
            cars_owned = int(rng.choice([0, 1], p=[0.92, 0.08]))
        else:
            cars_owned = int(rng.choice([0, 1], p=[0.98, 0.02]))
            
        hh = Household(
            id=hh_id,
            member_ids=[],
            has_car=(cars_owned > 0),
            cars_owned=cars_owned,
            cars_available=cars_owned,
        )

        hh_member_agents: list[Agent] = []

        # 2. Build agents for this household
        for member_idx in range(size):
            # Determine relationship, age, and occupation
            if size == 1:
                # Single individual
                age = int(rng.integers(21, 75))
                if age >= 60:
                    occupation = Occupation.RETIRED_CITIZEN
                elif age < 25:
                    occupation = Occupation.STUDENT
                else:
                    occupation = rng.choice(
                        [Occupation.OFFICE_EXECUTIVE, Occupation.BLUE_COLLAR_WORKER, Occupation.GIG_WORKER],
                        p=[0.35, 0.40, 0.25],
                    )
            else:
                # Family household
                if member_idx == 0:
                    # Head of household (working age)
                    age = int(rng.integers(25, 55))
                    occupation = rng.choice(
                        [Occupation.OFFICE_EXECUTIVE, Occupation.BLUE_COLLAR_WORKER, Occupation.GIG_WORKER],
                        p=[0.35, 0.45, 0.20],
                    )
                elif member_idx == 1:
                    # Spouse
                    age = int(max(20, min(70, rng.normal(hh_member_agents[0].age, 3))))
                    occupation = rng.choice(
                        [Occupation.OFFICE_EXECUTIVE, Occupation.BLUE_COLLAR_WORKER, Occupation.RETIRED_CITIZEN],
                        p=[0.25, 0.35, 0.40],  # Retired functions as stay-at-home here
                    )
                else:
                    # Child or Elderly Parent
                    is_elderly = rng.random() < 0.30
                    if is_elderly:
                        age = int(rng.integers(60, 80))
                        occupation = Occupation.RETIRED_CITIZEN
                    else:
                        age = int(max(5, min(24, rng.normal(hh_member_agents[0].age - 25, 5))))
                        if age < 23:
                            occupation = Occupation.STUDENT
                        else:
                            occupation = rng.choice(
                                [Occupation.BLUE_COLLAR_WORKER, Occupation.GIG_WORKER], p=[0.60, 0.40]
                            )

            # Income assignment
            if occupation == Occupation.STUDENT:
                income = 1
            elif occupation == Occupation.RETIRED_CITIZEN:
                income = max(1, hh_income - 1)
            else:
                income = max(1, min(5, hh_income + int(rng.choice([-1, 0, 1]))))

            # Node assignment
            home_node = int(rng.integers(0, n_nodes))
            work_node = int(rng.integers(0, n_nodes)) if occupation != Occupation.RETIRED_CITIZEN else None
            
            activity_locations = {ActivityType.HOME: home_node}
            if work_node is not None:
                activity_locations[ActivityType.WORK] = work_node

            # Activity schedule generation
            activities: list[Activity] = [Activity(ActivityType.HOME, home_node, 0, 0)]
            
            if occupation == Occupation.OFFICE_EXECUTIVE:
                leave_home = int(rng.normal(9 * 60, 30))  # 9:00 AM
                duration = int(rng.normal(9 * 60, 30))     # 9 hours
                activities.append(Activity(ActivityType.WORK, work_node, leave_home, duration))
                activities[0].duration_min = leave_home
            
            elif occupation == Occupation.STUDENT:
                school_node = int(rng.integers(0, n_nodes))
                activity_locations[ActivityType.EDUCATION] = school_node
                leave_home = int(rng.normal(10 * 60, 45))  # 10:00 AM
                duration = int(rng.normal(5 * 60, 30))     # 5 hours
                activities.append(Activity(ActivityType.EDUCATION, school_node, leave_home, duration))
                activities[0].duration_min = leave_home
                
                # 30% chance of evening recreation leg
                if rng.random() < 0.30:
                    rec_node = int(rng.integers(0, n_nodes))
                    activity_locations[ActivityType.RECREATION] = rec_node
                    rec_start = leave_home + duration + 30
                    activities.append(Activity(ActivityType.RECREATION, rec_node, rec_start, 90))
            
            elif occupation == Occupation.BLUE_COLLAR_WORKER:
                leave_home = int(rng.normal(8 * 60, 15))  # 8:00 AM
                duration = int(rng.normal(9 * 60, 15))     # 9 hours
                activities.append(Activity(ActivityType.WORK, work_node, leave_home, duration))
                activities[0].duration_min = leave_home
            
            elif occupation == Occupation.GIG_WORKER:
                # Gig workers travel to 3 work locations
                node_a = int(rng.integers(0, n_nodes))
                node_b = int(rng.integers(0, n_nodes))
                node_c = int(rng.integers(0, n_nodes))
                activity_locations[ActivityType.GIG_WORK] = node_a
                
                leave_home = int(rng.normal(11 * 60, 60))  # 11:00 AM
                activities.append(Activity(ActivityType.GIG_WORK, node_a, leave_home, 120))
                activities.append(Activity(ActivityType.GIG_WORK, node_b, leave_home + 150, 120))
                activities.append(Activity(ActivityType.GIG_WORK, node_c, leave_home + 300, 120))
                activities[0].duration_min = leave_home
                
            elif occupation == Occupation.RETIRED_CITIZEN:
                rec_node = int(rng.integers(0, n_nodes))
                activity_locations[ActivityType.RECREATION] = rec_node
                leave_home = int(rng.normal(11 * 60, 45))  # 11:00 AM
                activities.append(Activity(ActivityType.RECREATION, rec_node, leave_home, 120))
                activities[0].duration_min = leave_home

            schedule = ActivitySchedule(activities=activities, leave_home_min=activities[1].start_time_min if len(activities) > 1 else 9*60)

            # Vehicle availability rules
            has_car = False
            if hh.has_car and member_idx < 2:
                has_car = True

            has_bike = bool(rng.random() < P_BIKE_BY_INCOME[income])
            if occupation == Occupation.GIG_WORKER:
                has_bike = True  # Gig workers almost always have a two-wheeler

            agent = Agent(
                id=agent_id,
                home_node=home_node,
                work_node=work_node,
                income_bracket=income,
                age=age,
                household_id=hh_id,
                occupation=occupation,
                has_car=has_car,
                has_bike=has_bike,
                has_metro_pass=bool(rng.random() < P_METRO_PASS),
                schedule=schedule,
                weights=_sample_weights(occupation, rng),
                activity_locations=activity_locations,
                household=hh,
            )
            
            hh.member_ids.append(agent_id)
            hh_member_agents.append(agent)
            agents.append(agent)
            agent_id += 1

        # 3. Establish School Escort runs within this household
        parents = [a for a in hh_member_agents if a.occupation in {Occupation.OFFICE_EXECUTIVE, Occupation.BLUE_COLLAR_WORKER}]
        children = [a for a in hh_member_agents if a.occupation == Occupation.STUDENT and a.age < 15]
        
        if parents and children:
            parent = parents[0]
            child = children[0]
            
            # Establish escort linkage
            parent.child_ids.append(child.id)
            child.parent_id = parent.id
            
            # Insert school drop-off leg into parent schedule
            school_node = child.activity_locations.get(ActivityType.EDUCATION, child.home_node)
            parent_work_act = next((act for act in parent.schedule.activities if act.activity_type == ActivityType.WORK), None)
            
            if parent_work_act:
                escort_start = parent_work_act.start_time_min - 30
                escort_act = Activity(ActivityType.ESCORTING, school_node, escort_start, 20)
                parent.schedule.activities.insert(1, escort_act)
                parent.schedule.activities[0].duration_min = escort_start
                parent.activity_locations[ActivityType.ESCORTING] = school_node

        hh_id += 1

    return agents
