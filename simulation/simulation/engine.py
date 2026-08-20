"""Simulation Core Engine.

Implements the Mesa-backed UrbanModel and the MesaSimEngine adapter
satisfying the backend SimEngine Protocol.
"""

from __future__ import annotations

import random
from pathlib import Path

import mesa
import numpy as np

from simulation.network import MultiModalNetwork
from simulation.agents import (
    CitizenAgent,
    Occupation,
    Household,
    ActivityType,
    Activity,
    ActivitySchedule,
    UtilityWeights,
    ModeChoiceModel,
)
from simulation.economic_agents import (
    MesaStallOwner,
    MesaStoreManager,
    MesaStoreStaff,
    MesaDeliveryAgent,
    WholesaleSupplier,
    ShopChoiceModel,
)
import pandas as pd
from simulation.metrics import calculate_metrics

# Standard imports from the backend app schemas
from app.models.schemas import (
    AgentLeg,
    AgentPresence,
    Dwelling,
    Snapshot,
    GridCell,
    AggregateMetrics,
    Mode,
    ScenarioStatus,
    ScenarioConfig,
    Event,
    EventType,
)

# How many agents the map may follow individually. The rest of the population reaches the
# frontend only as aggregated grid cells (PROJECT_SPEC §16.1).
FOCUS_COHORT_SIZE = 250
# Cap on vertices per streamed leg, so one long route cannot blow up a frame. Roads are
# followed vertex by vertex, so this has to be generous enough to hold the bends — it is a
# ceiling for pathological routes, not a target.
MAX_POLYLINE_POINTS = 400

# Economic agents by class name -> the role the map draws them as.
_ECONOMIC_ROLES = {
    "MesaStallOwner": "stall_owner",
    "MesaStoreManager": "store_manager",
    "MesaStoreStaff": "store_staff",
    "MesaDeliveryAgent": "delivery_rider",
}

# Vehicle-ownership probability by income bracket (1=lowest .. 5=highest).
_P_BIKE_BY_INCOME = {1: 0.10, 2: 0.30, 3: 0.50, 4: 0.55, 5: 0.45}
_P_METRO_PASS = 0.25


def _sq_dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def _simplify(points: list[tuple[float, float]], limit: int) -> list[tuple[float, float]]:
    """Trim a polyline to ``limit`` vertices while keeping its shape.

    Sampling at even intervals is what makes a route cut corners — it is blind to which
    vertices carry the bends. This drops the vertices that deviate least from the line
    between their neighbours, so straight runs lose points and curves keep them.
    """
    if len(points) <= limit or limit < 3:
        return points

    def deviation(prev, cur, nxt) -> float:
        # Twice the triangle area: how far `cur` sits off the prev->nxt chord.
        return abs(
            (nxt[0] - prev[0]) * (prev[1] - cur[1]) - (prev[0] - cur[0]) * (nxt[1] - prev[1])
        )

    kept = list(points)
    while len(kept) > limit:
        # Never drop the endpoints.
        scores = [
            (deviation(kept[i - 1], kept[i], kept[i + 1]), i) for i in range(1, len(kept) - 1)
        ]
        _, drop_at = min(scores)
        kept.pop(drop_at)
    return kept


def _path_if_exists(path) -> str | None:
    """Optional inputs (transit feeds) are skipped rather than crashing the run."""
    return str(path) if path is not None and Path(path).exists() else None


def _enum_value(value) -> str:
    """Wire-friendly text for a plain ``(str, Enum)`` member ("student", not "Occupation.STUDENT")."""
    return str(getattr(value, "value", value))


def _pick_occupation(
    options: list[Occupation],
    probs: list[float],
    rng: np.random.Generator,
) -> Occupation:
    """Sample an Occupation enum from a weighted list using numpy.

    np.random.Generator.choice() corrupts enum objects into truncated np.str_
    values, so we sample an integer index instead and use it to index the list.
    """
    idx = int(rng.choice(len(options), p=probs))
    return options[idx]


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


class SimpleScheduler:
    """A clean, lightweight, deterministic agent scheduler."""

    def __init__(self, model: UrbanModel) -> None:
        self.model = model
        self.agents: list[mesa.Agent] = []

    def add(self, agent: mesa.Agent) -> None:
        self.agents.append(agent)

    def step(self) -> None:
        """Call step on each agent in insertion order."""
        for agent in self.agents:
            agent.step()


class UrbanModel(mesa.Model):
    """Mesa model representing the city's transport ecosystem."""

    def __init__(self, config: ScenarioConfig, data_paths=None) -> None:
        super().__init__()
        self.config = config
        self.data_paths = data_paths
        self.current_tick = 0
        # A run may begin partway through the day so a viewer is not staring at a
        # sleeping city; the clock is offset, the world still starts from tick 0.
        self.start_time_minutes = int(getattr(config, "start_time_minutes", 0) or 0)
        self.sim_time_minutes = self.start_time_minutes
        self.running = True

        # Initialize seeded RNG
        self._rng = random.Random(config.seed)
        self._np_rng = np.random.default_rng(config.seed)
        self.reset_random_system(config.seed)

        # 1. Physical spatial and multi-modal network.
        # network_paths (set explicitly on the scenario) wins; otherwise fall back to the
        # backend's resolved DataPaths, so `use_real_data: true` alone is enough to run on
        # real streets instead of the synthetic lattice.
        use_real = getattr(config, "use_real_data", False)
        graphml = config.network_paths.get("graphml") or (
            str(data_paths.road_network) if use_real and data_paths else None
        )
        metro_json = config.network_paths.get("metro_json") or (
            _path_if_exists(data_paths.metro_network) if use_real and data_paths else None
        )
        bus_json = config.network_paths.get("bus_json") or (
            _path_if_exists(data_paths.bus_routes) if use_real and data_paths else None
        )

        if use_real and graphml:
            self.network = MultiModalNetwork.load_from_osm(
                graphml_path=graphml,
                metro_json_path=metro_json,
                bus_json_path=bus_json,
            )
        else:
            self.network = MultiModalNetwork()

        # 2. Scheduler
        self.schedule = SimpleScheduler(self)

        # 3. Shared ModeChoiceModel (uses the seeded NumPy RNG)
        self.mode_choice_model = ModeChoiceModel(rng=self._np_rng)

        # 4. Dynamic metric tracking
        self.metrics = None
        # Setup empty initial metrics
        self.metrics = AggregateMetrics(
            tick=0,
            sim_time_minutes=0,
            rain_intensity=0.0,
            avg_commute_minutes=28.0,
            mode_share={},
            metro_load_pct=0.0,
            bus_load_pct=0.0,
            road_congestion_index=0.0,
            agents_commuting=0,
            aqi_estimate=0.0,
        )

        # 5. Household registry for daily resource resets
        self.households: dict[int, Household] = {}

        # 6. Track the last simulated day for daily hooks
        self._last_day = -1

        # 7. Economic Agent Registries
        self.stalls: dict[int, MesaStallOwner] = {}
        self.stores: dict[int, MesaStoreManager] = {}
        self.delivery_agents: dict[int, MesaDeliveryAgent] = {}
        self.economic_agents: dict[int, mesa.Agent] = {}
        self.supplier: WholesaleSupplier | None = None

        # 8. Shared ShopChoiceModel
        self.shop_choice_model = ShopChoiceModel(rng=self._np_rng)

        # 9. Generate or Load Population (same precedence as the network above).
        population_path = config.population_path or (
            _path_if_exists(data_paths.population) if use_real and data_paths else None
        )
        if use_real and population_path:
            self._load_real_population(population_path)
        else:
            self._generate_synthetic_population(config.population)

        # 10. Spawn Economic Agents
        self._spawn_economic_agents()

    def reset_random_system(self, seed: int) -> None:
        """Ensure standard libraries and NumPy share the scenario seed."""
        random.seed(seed)
        np.random.seed(seed)

    def _load_real_population(self, parquet_path: str) -> None:
        """Load agents from pre-generated parquet file with real OSM node IDs."""
        try:
            df = pd.read_parquet(parquet_path)
        except Exception as e:
            print(f"Warning: Failed to load {parquet_path}: {e}")
            self._generate_synthetic_population(self.config.population)
            return

        rng = self._np_rng

        # The parquet holds the full synthetic population; a scenario may ask for fewer
        # agents to stay inside the tick budget. Sample deterministically from the seed so
        # a smaller run is still reproducible.
        if 0 < self.config.population < len(df):
            df = df.sample(n=self.config.population, random_state=self.config.seed)

        # Map string occupations to the enum
        occ_map = {
            "Corporate": Occupation.OFFICE_EXECUTIVE,
            "Service": Occupation.BLUE_COLLAR_WORKER,
            "Student": Occupation.STUDENT,
            "Labor": Occupation.GIG_WORKER,
            "Unemployed": Occupation.UNEMPLOYED,
        }

        agent_id = 0
        hh_id = 0

        # The parquet holds OSM node ids captured when it was generated. Re-running the
        # network pipeline (OSM changes daily, and the strongly-connected-component trim
        # varies with it) can leave references to nodes this graph no longer has. Rather
        # than crash deep in a tick, snap each stale reference to the nearest real node.
        graph_nodes = self.network.g.nodes
        node_pool = list(graph_nodes)
        remapped = 0

        def _valid_node(node_id: str | None) -> str | None:
            nonlocal remapped
            if node_id is None or node_id in graph_nodes:
                return node_id
            remapped += 1
            return str(rng.choice(node_pool)) if node_pool else None

        for _, row in df.iterrows():
            # The population pipeline writes income_bracket as a human-readable band
            # ("20000-50000") and the 1-5 code the agents actually use alongside it.
            if "income_bracket_numeric" in row:
                income = int(row["income_bracket_numeric"])
            else:
                income = int(row["income_bracket"])
            age = int(row["age"])
            has_car = bool(row["has_car"])
            has_bike = bool(row["has_bike"])
            has_metro_pass = bool(row["has_metro_pass"])
            occ_str = str(row["occupation"])
            occupation = occ_map.get(occ_str, Occupation.BLUE_COLLAR_WORKER)

            # Node assignment (ensure strings for OSM IDs), repairing stale references.
            home_node = _valid_node(str(row["home_node"]))
            work_node = _valid_node(
                str(row["work_node"])
                if pd.notna(row["work_node"]) and str(row["work_node"]) != "nan"
                else None
            )
            if (
                occupation == Occupation.UNEMPLOYED
                or occupation == Occupation.RETIRED_CITIZEN
            ):
                work_node = None

            # Ensure home != work
            if work_node and work_node == home_node:
                pool = [n for n in self.network.g.nodes if n != home_node]
                if pool:
                    work_node = str(rng.choice(pool))

            # Fallback households: 1 agent = 1 household
            hh = Household(
                id=hh_id,
                member_ids=[agent_id],
                has_car=has_car,
                cars_owned=1 if has_car else 0,
                cars_available=1 if has_car else 0,
            )
            self.households[hh_id] = hh

            activity_locations = {ActivityType.HOME: home_node}
            if work_node is not None:
                activity_locations[ActivityType.WORK] = work_node

            # Build simple schedule
            activities = [Activity(ActivityType.HOME, home_node, 0, 0)]
            leave_home = int(rng.normal(9 * 60, 30))
            if work_node:
                activities.append(
                    Activity(ActivityType.WORK, work_node, leave_home, 9 * 60)
                )
                activities[0].duration_min = leave_home
            else:
                activities[0].duration_min = 24 * 60

            schedule = ActivitySchedule(
                activities=activities, leave_home_min=leave_home
            )

            agent = CitizenAgent(
                unique_id=agent_id,
                model=self,
                home_node=home_node,
                work_node=work_node,
                income_bracket=income,
                age=age,
                has_car=has_car,
                has_bike=has_bike,
                has_metro_pass=has_metro_pass,
                occupation=occupation,
                household_id=hh_id,
                household=hh,
                schedule=schedule,
                weights=_sample_weights(occupation, rng),
                activity_locations=activity_locations,
            )

            self.schedule.add(agent)
            agent_id += 1
            hh_id += 1

        if remapped:
            print(
                f"Note: {remapped} home/work references in {parquet_path} pointed at nodes "
                "missing from the road graph and were reassigned. Re-run "
                "data/pipelines/run_all.py --force to regenerate the population against "
                "the current network."
            )

    def _spawn_economic_agents(self) -> None:
        """Spawn Mesa-compatible economic agents (stalls, stores, delivery)."""
        rng = self._np_rng
        pop_size = len(self.schedule.agents)
        if pop_size == 0:
            pop_size = self.config.population

        num_stalls = int(pop_size * 0.05)
        num_managers = int(pop_size * 0.01)
        num_staff = int(pop_size * 0.02)
        num_delivery = int(pop_size * 0.02)

        candidates = []
        intersections = []
        for node_id, data in self.network.g.nodes(data=True):
            node_type = data.get("type")
            if node_type == "metro_station":
                candidates.append(str(node_id))
            elif node_type == "intersection":
                intersections.append(str(node_id))

        if not candidates:
            candidates = intersections
        if not candidates:
            return

        # 1. Supplier
        central_node = (
            str(rng.choice(intersections)) if intersections else str(candidates[0])
        )
        self.supplier = WholesaleSupplier(
            supplier_id=999999, location_node=central_node
        )

        agent_id_counter = 1000000

        # 2. Stalls
        stall_types = ["food", "clothes", "accessories"]
        stall_weights = [0.5, 0.3, 0.2]
        for _ in range(num_stalls):
            home_node = (
                str(rng.choice(intersections))
                if intersections
                else str(rng.choice(candidates))
            )
            vending_node = str(rng.choice(candidates))
            stype = stall_types[int(rng.choice(len(stall_types), p=stall_weights))]

            stall = MesaStallOwner(
                model=self,
                stall_id=agent_id_counter,
                home_node=home_node,
                vending_node=vending_node,
                stall_type=stype,
                inventory_decay_rate=(
                    0.15 if stype == "food" else (0.02 if stype == "clothes" else 0.01)
                ),
                disruption_probability=(
                    0.05 if stype == "food" else (0.08 if stype == "clothes" else 0.06)
                ),
            )
            self.schedule.add(stall)
            self.stalls[agent_id_counter] = stall
            self.economic_agents[agent_id_counter] = stall
            agent_id_counter += 1

        # 3. Stores & Staff
        staff_per_store = (
            max(1, num_staff // max(1, num_managers)) if num_managers > 0 else 0
        )
        for _ in range(num_managers):
            store_node = str(rng.choice(candidates))
            manager = MesaStoreManager(
                model=self, manager_id=agent_id_counter, store_node=store_node
            )
            self.schedule.add(manager)
            self.stores[agent_id_counter] = manager
            self.economic_agents[agent_id_counter] = manager
            agent_id_counter += 1

            for _ in range(staff_per_store):
                home_node = (
                    str(rng.choice(intersections))
                    if intersections
                    else str(rng.choice(candidates))
                )
                staff = MesaStoreStaff(
                    model=self,
                    staff_id=agent_id_counter,
                    home_node=home_node,
                    store_node=store_node,
                )
                manager.staff_ids.append(agent_id_counter)
                self.schedule.add(staff)
                self.economic_agents[agent_id_counter] = staff
                agent_id_counter += 1

        # 4. Delivery Agents
        for _ in range(num_delivery):
            home_node = (
                str(rng.choice(intersections))
                if intersections
                else str(rng.choice(candidates))
            )
            delivery = MesaDeliveryAgent(
                model=self, delivery_id=agent_id_counter, home_node=home_node
            )
            self.schedule.add(delivery)
            self.delivery_agents[agent_id_counter] = delivery
            self.economic_agents[agent_id_counter] = delivery
            agent_id_counter += 1

    def _generate_synthetic_population(self, population_size: int) -> None:
        """Create a diverse, demographic-typical population of commuting agents.

        Port of SUB-02's build_population() adapted to use the simulation's
        network nodes and Mesa agent system. Features:
        - Household generation with Indian metro-area size distribution
        - Per-household car ownership by income bracket
        - Occupation assignment by family role (head, spouse, child, elderly)
        - Multi-leg ActivitySchedule construction per occupation archetype
        - Escort linkages (parent drops child at school)
        - UtilityWeights with per-agent Gaussian jitter
        """
        rng = self._np_rng

        # Retrieve physical road nodes for home/work assignments
        intersection_nodes = [
            node_id
            for node_id, data in self.network.g.nodes(data=True)
            if data.get("type") == "intersection"
        ]

        if not intersection_nodes:
            raise ValueError("No road intersection nodes available in network.")

        n_nodes = len(intersection_nodes)

        # 1. Generate household size distribution
        # Reflecting typical sizes in Indian metropolitan areas
        hh_sizes: list[int] = []
        while sum(hh_sizes) < population_size:
            hh_sizes.append(
                int(rng.choice([1, 2, 3, 4, 5], p=[0.15, 0.25, 0.25, 0.20, 0.15]))
            )

        if sum(hh_sizes) > population_size:
            hh_sizes[-1] -= sum(hh_sizes) - population_size
            if hh_sizes[-1] <= 0:
                hh_sizes.pop()

        agent_id = 0
        hh_id = 0

        for size in hh_sizes:
            # Sample household income bracket (1..5)
            hh_income = int(
                rng.choice(np.arange(1, 6), p=[0.20, 0.30, 0.25, 0.15, 0.10])
            )

            # Decide car capacity for household
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

            hh_member_agents: list[CitizenAgent] = []

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
                        occupation = _pick_occupation(
                            [
                                Occupation.OFFICE_EXECUTIVE,
                                Occupation.BLUE_COLLAR_WORKER,
                                Occupation.GIG_WORKER,
                            ],
                            [0.35, 0.40, 0.25],
                            rng,
                        )
                else:
                    # Family household
                    if member_idx == 0:
                        # Head of household (working age)
                        age = int(rng.integers(25, 55))
                        occupation = _pick_occupation(
                            [
                                Occupation.OFFICE_EXECUTIVE,
                                Occupation.BLUE_COLLAR_WORKER,
                                Occupation.GIG_WORKER,
                            ],
                            [0.35, 0.45, 0.20],
                            rng,
                        )
                    elif member_idx == 1:
                        # Spouse
                        age = int(
                            max(20, min(70, rng.normal(hh_member_agents[0].age, 3)))
                        )
                        occupation = _pick_occupation(
                            [
                                Occupation.OFFICE_EXECUTIVE,
                                Occupation.BLUE_COLLAR_WORKER,
                                Occupation.RETIRED_CITIZEN,
                            ],
                            [0.25, 0.35, 0.40],
                            rng,
                        )
                    else:
                        # Child or Elderly Parent
                        is_elderly = rng.random() < 0.30
                        if is_elderly:
                            age = int(rng.integers(60, 80))
                            occupation = Occupation.RETIRED_CITIZEN
                        else:
                            age = int(
                                max(
                                    5,
                                    min(
                                        24, rng.normal(hh_member_agents[0].age - 25, 5)
                                    ),
                                )
                            )
                            if age < 23:
                                occupation = Occupation.STUDENT
                            else:
                                occupation = _pick_occupation(
                                    [
                                        Occupation.BLUE_COLLAR_WORKER,
                                        Occupation.GIG_WORKER,
                                    ],
                                    [0.60, 0.40],
                                    rng,
                                )

                # Income assignment
                if occupation == Occupation.STUDENT:
                    income = 1
                elif occupation == Occupation.RETIRED_CITIZEN:
                    income = max(1, hh_income - 1)
                else:
                    income = max(1, min(5, hh_income + int(rng.choice([-1, 0, 1]))))

                # Node assignment — use real intersection node IDs
                home_node = intersection_nodes[int(rng.integers(0, n_nodes))]
                work_node = (
                    intersection_nodes[int(rng.integers(0, n_nodes))]
                    if occupation != Occupation.RETIRED_CITIZEN
                    else None
                )
                # Ensure home != work
                if work_node and work_node == home_node:
                    pool = [n for n in intersection_nodes if n != home_node]
                    work_node = pool[int(rng.integers(0, len(pool)))]

                activity_locations: dict[ActivityType, str] = {
                    ActivityType.HOME: home_node
                }
                if work_node is not None:
                    activity_locations[ActivityType.WORK] = work_node

                # Activity schedule generation per occupation archetype
                activities: list[Activity] = [
                    Activity(ActivityType.HOME, home_node, 0, 0)
                ]

                if occupation == Occupation.OFFICE_EXECUTIVE:
                    leave_home = int(rng.normal(9 * 60, 30))  # 9:00 AM
                    duration = int(rng.normal(9 * 60, 30))  # 9 hours
                    activities.append(
                        Activity(ActivityType.WORK, work_node, leave_home, duration)
                    )
                    activities[0].duration_min = leave_home

                elif occupation == Occupation.STUDENT:
                    school_node = intersection_nodes[int(rng.integers(0, n_nodes))]
                    activity_locations[ActivityType.EDUCATION] = school_node
                    leave_home = int(rng.normal(10 * 60, 45))  # 10:00 AM
                    duration = int(rng.normal(5 * 60, 30))  # 5 hours
                    activities.append(
                        Activity(
                            ActivityType.EDUCATION, school_node, leave_home, duration
                        )
                    )
                    activities[0].duration_min = leave_home

                    # 30% chance of evening recreation leg
                    if rng.random() < 0.30:
                        rec_node = intersection_nodes[int(rng.integers(0, n_nodes))]
                        activity_locations[ActivityType.RECREATION] = rec_node
                        rec_start = leave_home + duration + 30
                        activities.append(
                            Activity(ActivityType.RECREATION, rec_node, rec_start, 90)
                        )

                elif occupation == Occupation.BLUE_COLLAR_WORKER:
                    leave_home = int(rng.normal(8 * 60, 15))  # 8:00 AM
                    duration = int(rng.normal(9 * 60, 15))  # 9 hours
                    activities.append(
                        Activity(ActivityType.WORK, work_node, leave_home, duration)
                    )
                    activities[0].duration_min = leave_home

                elif occupation == Occupation.GIG_WORKER:
                    # Gig workers travel to 3 work locations
                    node_a = intersection_nodes[int(rng.integers(0, n_nodes))]
                    node_b = intersection_nodes[int(rng.integers(0, n_nodes))]
                    node_c = intersection_nodes[int(rng.integers(0, n_nodes))]
                    activity_locations[ActivityType.GIG_WORK] = node_a

                    leave_home = int(rng.normal(11 * 60, 60))  # 11:00 AM
                    activities.append(
                        Activity(ActivityType.GIG_WORK, node_a, leave_home, 120)
                    )
                    activities.append(
                        Activity(ActivityType.GIG_WORK, node_b, leave_home + 150, 120)
                    )
                    activities.append(
                        Activity(ActivityType.GIG_WORK, node_c, leave_home + 300, 120)
                    )
                    activities[0].duration_min = leave_home

                elif occupation == Occupation.RETIRED_CITIZEN:
                    rec_node = intersection_nodes[int(rng.integers(0, n_nodes))]
                    activity_locations[ActivityType.RECREATION] = rec_node
                    leave_home = int(rng.normal(11 * 60, 45))  # 11:00 AM
                    activities.append(
                        Activity(ActivityType.RECREATION, rec_node, leave_home, 120)
                    )
                    activities[0].duration_min = leave_home

                schedule = ActivitySchedule(
                    activities=activities,
                    leave_home_min=(
                        activities[1].start_time_min if len(activities) > 1 else 9 * 60
                    ),
                )

                # Vehicle availability rules
                has_car = False
                if hh.has_car and member_idx < 2:
                    has_car = True

                has_bike = bool(rng.random() < _P_BIKE_BY_INCOME[income])
                if occupation == Occupation.GIG_WORKER:
                    has_bike = True  # Gig workers almost always have a two-wheeler

                agent = CitizenAgent(
                    unique_id=agent_id,
                    model=self,
                    home_node=home_node,
                    work_node=work_node,
                    income_bracket=income,
                    age=age,
                    has_car=has_car,
                    has_bike=has_bike,
                    has_metro_pass=bool(rng.random() < _P_METRO_PASS),
                    occupation=occupation,
                    household_id=hh_id,
                    household=hh,
                    schedule=schedule,
                    weights=_sample_weights(occupation, rng),
                    activity_locations=activity_locations,
                )

                hh.member_ids.append(agent_id)
                hh_member_agents.append(agent)
                self.schedule.add(agent)
                agent_id += 1

            # 3. Establish School Escort runs within this household
            parents = [
                a
                for a in hh_member_agents
                if a.occupation
                in {Occupation.OFFICE_EXECUTIVE, Occupation.BLUE_COLLAR_WORKER}
            ]
            children = [
                a
                for a in hh_member_agents
                if a.occupation == Occupation.STUDENT and a.age < 15
            ]

            if parents and children:
                parent = parents[0]
                child = children[0]

                # Establish escort linkage
                parent.child_ids.append(child.unique_id)
                child.parent_id = parent.unique_id

                # Insert school drop-off leg into parent schedule
                school_node = child.activity_locations.get(
                    ActivityType.EDUCATION, child.home_node
                )
                parent_work_act = next(
                    (
                        act
                        for act in parent.schedule.activities
                        if act.activity_type == ActivityType.WORK
                    ),
                    None,
                )

                if parent_work_act:
                    escort_start = parent_work_act.start_time_min - 30
                    escort_act = Activity(
                        ActivityType.ESCORTING, school_node, escort_start, 20
                    )
                    parent.schedule.activities.insert(1, escort_act)
                    parent.schedule.activities[0].duration_min = escort_start
                    parent.activity_locations[ActivityType.ESCORTING] = school_node

            # Register household
            self.households[hh_id] = hh
            hh_id += 1

    def step(self) -> None:
        """Advance the Mesa model exactly one step."""
        # 0. Daily hooks — reset household resources and adapt agent behavior
        current_day = self.sim_time_minutes // (24 * 60)
        if current_day > self._last_day:
            if self._last_day >= 0:
                # Not the first day — perform night reset
                self._night_reset()
            self._last_day = current_day
            for hh in self.households.values():
                hh.reset_daily_resources()
            for agent in self.schedule.agents:
                if hasattr(agent, "adapt_behavior"):
                    agent.adapt_behavior()

        # Phase 2: Reset per-tick metro boarding counters (SUB-03, task 3.2)
        self.network.reset_metro_load_tracking()

        # 1. Step the scheduler (activates all agents)
        self.schedule.step()

        # 2. Update physical road flow and travel times
        active_commuters = [
            a
            for a in self.schedule.agents
            if getattr(a, "state", None) == "COMMUTING" and hasattr(a, "current_route")
        ]
        self.network.update_road_congestion(active_commuters)

        # Phase 2: Advance bus vehicles for bunching simulation (SUB-03, task 3.3)
        self.network.step_bus_vehicles(
            tick=self.current_tick,
            rain_intensity=self.network.weather_rain_intensity,
        )

        # 3. Calculate aggregate metrics
        met_dict = calculate_metrics(self)
        self.metrics = AggregateMetrics(**met_dict)

    def _night_reset(self) -> None:
        """Reset the world state at the start of a new simulation day.

        All agents return home, edge flows reset, and routing cache is
        cleared. Agent memory is preserved across days so commuters
        remember yesterday's frustrations and can adapt.
        """
        # Reset all agents to home
        for agent in self.schedule.agents:
            agent.reset_for_new_day()

        # Reset all edge flows
        for u, v in self.network.g.edges:
            self.network.g.edges[u, v]["flow"] = 0

        # Clear routing cache
        self.network.clear_routing_cache()


class MesaSimEngine:
    """Simulation Engine implementation satisfying the SimEngine protocol.

    Wraps the Mesa UrbanModel with REST and WebSocket serializer mappings.
    """

    def __init__(self, config: ScenarioConfig, data_paths=None) -> None:
        self.config = config
        self.model = UrbanModel(config, data_paths=data_paths)
        self._pending_events: list[Event] = []
        self._focus_ids: frozenset[int] = self._pick_focus_cohort()
        self._dwellings_cache: dict[str, Dwelling] | None = None

        # Phase 2: Auto-load DMRC schedule if available (SUB-03, task 3.1)
        self._load_dmrc_schedule()

    def _load_dmrc_schedule(self) -> None:
        """Auto-discover and load the DMRC schedule JSON file.

        Searches for dmrc_schedule.json in:
        1. simulation/data/ relative to this module
        2. data/ directory relative to this module
        """
        from pathlib import Path

        # Try simulation/data/dmrc_schedule.json relative to this file
        module_dir = Path(__file__).resolve().parent
        candidates = [
            module_dir.parent / "data" / "dmrc_schedule.json",
            module_dir / "data" / "dmrc_schedule.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                self.model.network.load_dmrc_schedule(candidate)
                return

    @property
    def current_tick(self) -> int:
        return self.model.current_tick

    def queue_event(self, event: Event) -> int:
        """Enqueues an incoming policy/weather/infra event for next tick boundary."""
        self._pending_events.append(event)
        return self.model.current_tick + 1

    def step(self) -> Snapshot:
        """Advance time by one tick, applying queued events."""
        # 1. Advance tick count and time
        self.model.current_tick += 1
        self.model.sim_time_minutes = (
            self.model.start_time_minutes + self.model.current_tick * self.config.tick_minutes
        )

        # 2. Process event dispatcher
        self._dispatch_events()

        # 3. Advance Mesa world step
        self.model.step()

        # 4. Return current snapshot
        return self.snapshot()

    def snapshot(self) -> Snapshot:
        """Return the current high-fidelity snapshot of the city state."""
        return Snapshot(
            scenario_id="",  # filled by scenario manager
            tick=self.model.current_tick,
            sim_time_minutes=self.model.sim_time_minutes,
            status=ScenarioStatus.running,
            metrics=self.model.metrics,
            grid=self._generate_grid_cells(),
            agent_legs=self.active_agent_legs(),
            presences=self.focus_presences(),
            dwellings=self.focus_dwellings(),
        )

    # --- focus cohort (individually rendered agents) ----------------------------------
    def _pick_focus_cohort(self) -> frozenset[int]:
        """Choose the agents the map may follow individually.

        Deterministic in the scenario seed, so the same run always follows the same
        citizens and the frontend can keep stable identities across reconnects.
        """
        citizens = sorted(
            a.unique_id
            for a in self.model.schedule.agents
            if isinstance(a, CitizenAgent)
        )
        limit = getattr(self.config, "max_tracked_agents", FOCUS_COHORT_SIZE)
        if len(citizens) <= limit:
            return frozenset(citizens)
        rng = np.random.default_rng(self.config.seed)
        picked = rng.choice(len(citizens), size=limit, replace=False)
        return frozenset(citizens[i] for i in picked)

    def _route_polyline(self, route: list[str]) -> list[tuple[float, float]]:
        """Convert a node-id route into the line a vehicle actually drives.

        Intersections alone are not the road: 42% of the OSM edges here are curved, so
        joining consecutive intersections with straight chords sends traffic through
        buildings. Each edge contributes its real shape where one is recorded.
        """
        graph = self.model.network.g
        nodes = graph.nodes

        def node_point(node_id: str) -> tuple[float, float] | None:
            data = nodes.get(node_id)
            if data and "lat" in data and "lon" in data:
                return (float(data["lat"]), float(data["lon"]))
            return None

        out: list[tuple[float, float]] = []
        for index, node_id in enumerate(route):
            point = node_point(node_id)
            if point is None:
                continue
            if not out or out[-1] != point:
                out.append(point)

            if index + 1 >= len(route):
                break

            next_id = route[index + 1]
            edge = graph.edges.get((node_id, next_id)) if graph.has_edge(node_id, next_id) else None
            shape = (edge or {}).get("shape") or []
            if len(shape) < 3:
                continue

            # OSM stores a way's geometry in its own direction; align it with travel.
            first, last = shape[0], shape[-1]
            nxt = node_point(next_id)
            if nxt is not None and _sq_dist(first, point) > _sq_dist(last, point):
                shape = list(reversed(shape))

            for vertex in shape[1:-1]:
                vertex = (float(vertex[0]), float(vertex[1]))
                if vertex != out[-1]:
                    out.append(vertex)

        # 6 decimal places is ~11 cm on the ground — far finer than a lane — and roughly
        # halves the bytes, because a raw float serialises as 28.631635000000002.
        return [(round(lat, 6), round(lon, 6)) for lat, lon in _simplify(out, MAX_POLYLINE_POINTS)]

    def active_agent_legs(self) -> list[AgentLeg]:
        """Legs currently under way for the focus cohort.

        The client animates along each polyline using simulated time, which is why the
        engine's own travel-time estimate is shipped with the geometry.
        """
        legs: list[AgentLeg] = []
        net = self.model.network
        for agent in self.model.schedule.agents:
            if agent.unique_id not in self._focus_ids:
                continue
            if getattr(agent, "state", None) != "COMMUTING":
                continue
            route = getattr(agent, "current_route", None)
            if not route or len(route) < 2:
                continue

            polyline = self._route_polyline(route)
            if len(polyline) < 2:
                continue

            mode_name = getattr(agent, "current_mode", None) or "walk"
            try:
                mode = Mode(mode_name)
            except ValueError:
                mode = Mode.walk

            duration = net.calculate_path_travel_time(route, mode_name)
            if duration <= 0:
                # A zero-length estimate would make the client divide by zero; one tick
                # is the shortest journey the engine can actually represent.
                duration = float(self.config.tick_minutes)

            legs.append(
                AgentLeg(
                    agent_id=str(agent.unique_id),
                    mode=mode,
                    occupation=_enum_value(getattr(agent, "occupation", "")),
                    destination_activity=self._destination_activity(agent),
                    start_minute=int(getattr(agent, "commute_start_time", 0)),
                    duration_minutes=float(duration),
                    polyline=polyline,
                )
            )
        return legs

    def focus_presences(self) -> list[AgentPresence]:
        """Where tracked agents are when they are not on the road, and what they're doing.

        Includes the working city — stall owners, shopkeepers, shop staff and delivery
        riders — which the simulation has always created but never showed anyone.
        """
        out: list[AgentPresence] = []
        nodes = self.model.network.g.nodes

        for agent in self.model.schedule.agents:
            presence = self._economic_presence(agent, nodes)
            if presence is not None:
                out.append(presence)

        for agent in self.model.schedule.agents:
            if agent.unique_id not in self._focus_ids:
                continue
            state = getattr(agent, "state", None)
            if state not in ("AT_HOME", "AT_WORK"):
                continue

            at_home = state == "AT_HOME"
            node_id = agent.home_node if at_home else (agent.work_node or agent.home_node)
            data = nodes.get(node_id)
            if not data or "lat" not in data:
                continue

            out.append(
                AgentPresence(
                    agent_id=str(agent.unique_id),
                    place="home" if at_home else "away",
                    activity=agent.current_activity_label(),
                    lat=float(data["lat"]),
                    lon=float(data["lon"]),
                    role="citizen",
                    detail={
                        "Occupation": _enum_value(getattr(agent, "occupation", "")).replace(
                            "_", " "
                        ),
                        "Age": str(getattr(agent, "age", "")),
                        "Household": f"#{getattr(agent, 'household_id', 0)}",
                    },
                )
            )
        return out

    def _economic_presence(self, agent, nodes) -> AgentPresence | None:
        """Render one economic agent, or None if this agent is not one.

        These agents never commute in the CitizenAgent sense — they hold a position (a
        stall pitch, a shop, a delivery depot) and their interesting state is commercial:
        stock, takings, whether they have gone bust.
        """
        role = _ECONOMIC_ROLES.get(type(agent).__name__)
        if role is None:
            return None

        # Each economic agent names its position differently: a stall owner moves between
        # home and a pitch, a manager is defined by their store.
        node_id = next(
            (
                getattr(agent, attr, None)
                for attr in ("current_location", "store_node", "vending_node", "home_node")
                if getattr(agent, attr, None)
            ),
            None,
        )
        data = nodes.get(node_id)
        if not data or "lat" not in data:
            return None

        detail: dict[str, str] = {}
        activity = role.replace("_", " ").title()
        place = "depot"

        if role == "stall_owner":
            place = "stall"
            stall_type = str(getattr(agent, "stall_type", "food"))
            if getattr(agent, "is_bankrupt", False):
                activity = f"Shuttered {stall_type} stall - went bust"
            elif getattr(agent, "is_disrupted_today", False):
                activity = f"{stall_type.title()} stall closed today - disruption"
            else:
                activity = f"Running a {stall_type} stall"
            detail = {
                "Stall type": stall_type,
                "Stock": f"{float(getattr(agent, 'inventory', 0.0)) * 100:.0f}%",
                "Cash": f"Rs {float(getattr(agent, 'cash_balance', 0.0)):,.0f}",
            }
        elif role == "store_manager":
            place = "store"
            activity = "Minding the shop"
            detail = {
                "Stock": f"{float(getattr(agent, 'inventory', 0.0)) * 100:.0f}%",
                "Cash": f"Rs {float(getattr(agent, 'cash_balance', 0.0)):,.0f}",
            }
        elif role == "store_staff":
            place = "store"
            activity = "On shift at the shop"
            wage = getattr(agent, "daily_wage", None)
            if wage is not None:
                detail = {"Daily wage": f"Rs {float(wage):,.0f}"}
        elif role == "delivery_rider":
            place = "depot"
            done = int(getattr(agent, "completed_deliveries", 0))
            activity = "Waiting for an order" if done == 0 else f"Between drops ({done} today)"
            detail = {
                "Deliveries": str(done),
                "Earnings": f"Rs {float(getattr(agent, 'earnings', 0.0)):,.0f}",
            }

        return AgentPresence(
            agent_id=str(agent.unique_id),
            place=place,
            activity=activity,
            lat=float(data["lat"]),
            lon=float(data["lon"]),
            role=role,
            detail=detail,
        )

    def focus_dwellings(self) -> dict[str, Dwelling]:
        """Every focus citizen's home. Static for the run, so the client caches it."""
        if self._dwellings_cache is not None:
            return self._dwellings_cache

        nodes = self.model.network.g.nodes
        out: dict[str, Dwelling] = {}
        for agent in self.model.schedule.agents:
            if agent.unique_id not in self._focus_ids:
                continue
            dwelling = getattr(agent, "dwelling", None)
            data = nodes.get(getattr(agent, "home_node", None))
            if dwelling is None or not data or "lat" not in data:
                continue
            out[str(agent.unique_id)] = Dwelling(
                kind=dwelling.kind,
                income_bracket=dwelling.bracket,
                area_sqm=dwelling.area_sqm,
                storeys=dwelling.storeys,
                rooms=list(dwelling.rooms),
                lat=float(data["lat"]),
                lon=float(data["lon"]),
            )
        self._dwellings_cache = out
        return out

    @staticmethod
    def _destination_activity(agent) -> str:
        """Human-readable label for where this leg is heading."""
        schedule = getattr(agent, "schedule", None)
        legs = schedule.get_legs() if schedule is not None else []
        idx = getattr(agent, "_current_leg_index", 0)
        if legs and 0 <= idx < len(legs):
            return _enum_value(legs[idx][1].activity_type)
        return "WORK" if getattr(agent, "state", "") == "COMMUTING" else "HOME"

    def _dispatch_events(self) -> None:
        """Dispatch and apply queued events directly to network structures."""
        for ev in self._pending_events:
            p = ev.payload
            net = self.model.network

            if ev.type == EventType.weather:
                net.weather_rain_intensity = float(
                    p.get("rain_intensity", net.weather_rain_intensity)
                )

            elif ev.type == EventType.policy:
                if "bus_capacity_pct" in p:
                    net.bus_capacity_multiplier = float(p["bus_capacity_pct"])
                if "fuel_price_delta_paise" in p:
                    net.fuel_price_delta_paise = int(p["fuel_price_delta_paise"])

            elif ev.type == EventType.infrastructure:
                line = p.get("disable_metro_line")
                if isinstance(line, str):
                    net.disabled_metro_lines.add(line)
                line = p.get("enable_metro_line")
                if isinstance(line, str):
                    net.disabled_metro_lines.discard(line)

        self._pending_events.clear()

    def _generate_grid_cells(self) -> list[GridCell]:
        """Aggregate high-resolution agent locations into a 10x10 coarse visualization grid."""
        GRID_ROWS, GRID_COLS = 10, 10

        # Use the network's dynamic bounding box (works for both synthetic and real data)
        net = self.model.network
        lat_start = net.lat_min
        lon_start = net.lon_min
        lat_span = max(0.001, net.lat_max - net.lat_min)
        lon_span = max(0.001, net.lon_max - net.lon_min)
        lat_step = lat_span / GRID_ROWS
        lon_step = lon_span / GRID_COLS

        # Initialize grid structures
        cells = []
        grid_data = [
            [
                {"density": 0, "congestion_sum": 0.0, "road_count": 0}
                for _ in range(GRID_COLS)
            ]
            for _ in range(GRID_ROWS)
        ]

        # 1. Map agent physical locations to grid bins
        for agent in self.model.schedule.agents:
            if hasattr(agent, "current_route"):
                node_id = (
                    agent.current_route[agent.route_index]
                    if (
                        getattr(agent, "state", None) == "COMMUTING"
                        and getattr(agent, "current_route", None)
                    )
                    else agent.home_node
                )
            else:
                node_id = getattr(
                    agent,
                    "current_location",
                    getattr(agent, "store_node", getattr(agent, "home_node", None)),
                )

            if not node_id:
                continue

            # Retrieve node coordinates. A node can be absent if the population parquet was
            # generated against a different vintage of the OSM graph; one stale reference
            # must not take down the whole snapshot.
            node_data = self.model.network.g.nodes.get(node_id)
            if not node_data or "lat" not in node_data:
                continue
            lat, lon = node_data["lat"], node_data["lon"]

            r = int(np.clip((lat - lat_start) / lat_step, 0, GRID_ROWS - 1))
            c = int(np.clip((lon - lon_start) / lon_step, 0, GRID_COLS - 1))
            grid_data[r][c]["density"] += 1

        # 2. Map road segment congestions to grid bins
        for u, v, edge_data in self.model.network.g.edges(data=True):
            if edge_data.get("type") == "road":
                u_lat = self.model.network.g.nodes[u]["lat"]
                u_lon = self.model.network.g.nodes[u]["lon"]

                r = int(np.clip((u_lat - lat_start) / lat_step, 0, GRID_ROWS - 1))
                c = int(np.clip((u_lon - lon_start) / lon_step, 0, GRID_COLS - 1))

                flow = edge_data.get("flow", 0)
                capacity = edge_data.get("capacity", 100.0)
                congestion = flow / max(10.0, capacity)

                grid_data[r][c]["congestion_sum"] += congestion
                grid_data[r][c]["road_count"] += 1

        # 3. Build and return serializable GridCell list
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                cell_lat = lat_start + r * lat_step
                cell_lon = lon_start + c * lon_step
                data = grid_data[r][c]

                avg_congestion = (
                    (data["congestion_sum"] / data["road_count"])
                    if data["road_count"] > 0
                    else 0.0
                )
                # Cap congestion between 0.0 and 1.0
                avg_congestion = min(1.0, max(0.0, avg_congestion))

                # Boost congestion index with rain intensity
                rain = self.model.network.weather_rain_intensity
                if rain > 0:
                    avg_congestion = min(1.0, avg_congestion + 0.25 * rain)

                cells.append(
                    GridCell(
                        lat=cell_lat,
                        lon=cell_lon,
                        density=data["density"],
                        congestion=round(avg_congestion, 3),
                    )
                )

        return cells
