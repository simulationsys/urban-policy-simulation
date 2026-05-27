"""Simulation Core Engine.

Implements the Mesa-backed UrbanModel and the MesaSimEngine adapter
satisfying the backend SimEngine Protocol.
"""

from __future__ import annotations

import random
import mesa
import numpy as np

from simulation.network import MultiModalNetwork, CITY_LAT, CITY_LON
from simulation.agents import CitizenAgent
from simulation.metrics import calculate_metrics

# Standard imports from the backend app schemas
from app.models.schemas import (
    Snapshot,
    GridCell,
    AggregateMetrics,
    ScenarioStatus,
    ScenarioConfig,
    Event,
    EventType,
)


class SimpleScheduler:
    """A clean, lightweight, deterministic agent scheduler."""

    def __init__(self, model: UrbanModel) -> None:
        self.model = model
        self.agents: list[CitizenAgent] = []

    def add(self, agent: CitizenAgent) -> None:
        self.agents.append(agent)

    def step(self) -> None:
        """Call step on each agent in insertion order."""
        for agent in self.agents:
            agent.step()


class UrbanModel(mesa.Model):
    """Mesa model representing the city's transport ecosystem."""

    def __init__(self, config: ScenarioConfig) -> None:
        super().__init__()
        self.config = config
        self.current_tick = 0
        self.sim_time_minutes = 0
        self.running = True

        # Initialize seeded RNG
        self._rng = random.Random(config.seed)
        self.reset_random_system(config.seed)

        # 1. Physical spatial and multi-modal network
        self.network = MultiModalNetwork()

        # 2. Scheduler
        self.schedule = SimpleScheduler(self)

        # 3. Dynamic metric tracking
        self.metrics = None
        # Setup empty initial metrics
        self.metrics = AggregateMetrics(
            tick=0,
            sim_time_minutes=0,
            rain_intensity=0.0,
            avg_commute_minutes=28.0,
            mode_share={},
            metro_load_pct=0.0,
            road_congestion_index=0.0,
            agents_commuting=0,
        )

        # 4. Generate Synthetic Population of Citizen Agents
        self._generate_synthetic_population(config.population)

    def reset_random_system(self, seed: int) -> None:
        """Ensure standard libraries and NumPy share the scenario seed."""
        random.seed(seed)
        np.random.seed(seed)

    def _generate_synthetic_population(self, population_size: int) -> None:
        """Create a diverse, demographic-typical population of commuting agents."""
        # Retrieve physical road nodes for home/work assignments
        intersection_nodes = [
            node_id
            for node_id, data in self.network.g.nodes(data=True)
            if data.get("type") == "intersection"
        ]

        if not intersection_nodes:
            raise ValueError("No road intersection nodes available in network.")

        for i in range(population_size):
            # Demographics
            # Age: 18 to 70
            age = self._rng.randint(18, 70)

            # Income Bracket: 1 to 5 (following bell curve)
            income_bracket = int(np.clip(round(self._rng.gauss(3.0, 1.0)), 1, 5))

            # Home and Work nodes (strictly different)
            home_node = self._rng.choice(intersection_nodes)
            work_nodes_pool = [n for n in intersection_nodes if n != home_node]
            work_node = self._rng.choice(work_nodes_pool)

            # Asset Ownership based on income bracket
            # Bracket 1-2 (Low income): Walk, bike, bus dominant
            # Bracket 3 (Middle income): Moderate car, high bike, high transit pass
            # Bracket 4-5 (High income): Car/auto dominant
            has_car = False
            has_bike = False
            has_metro_pass = False

            if income_bracket in (1, 2):
                has_bike = self._rng.random() < 0.60
                has_metro_pass = self._rng.random() < 0.15
            elif income_bracket == 3:
                has_car = self._rng.random() < 0.40
                has_bike = self._rng.random() < 0.40
                has_metro_pass = self._rng.random() < 0.50
            else:  # 4 and 5
                has_car = self._rng.random() < 0.85
                has_bike = self._rng.random() < 0.15
                has_metro_pass = self._rng.random() < 0.20

            agent = CitizenAgent(
                unique_id=i,
                model=self,
                home_node=home_node,
                work_node=work_node,
                income_bracket=income_bracket,
                age=age,
                has_car=has_car,
                has_bike=has_bike,
                has_metro_pass=has_metro_pass,
            )
            self.schedule.add(agent)

    def step(self) -> None:
        """Advance the Mesa model exactly one step."""
        # 1. Step the scheduler (activates all agents)
        self.schedule.step()

        # 2. Update physical road flow and travel times
        active_commuters = [a for a in self.schedule.agents if a.state == "COMMUTING"]
        self.network.update_road_congestion(active_commuters)

        # 3. Calculate aggregate metrics
        met_dict = calculate_metrics(self)
        self.metrics = AggregateMetrics(**met_dict)


class MesaSimEngine:
    """Simulation Engine implementation satisfying the SimEngine protocol.

    Wraps the Mesa UrbanModel with REST and WebSocket serializer mappings.
    """

    def __init__(self, config: ScenarioConfig) -> None:
        self.config = config
        self.model = UrbanModel(config)
        self._pending_events: list[Event] = []

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
        self.model.sim_time_minutes = self.model.current_tick * self.config.tick_minutes

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
        )

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
        """Aggregate high-resolution agent locations into an 8x8 coarse visualization grid."""
        GRID_ROWS, GRID_COLS = 8, 8
        lat_start = CITY_LAT - (GRID_ROWS / 2) * 0.01
        lon_start = CITY_LON - (GRID_COLS / 2) * 0.01

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
            node_id = (
                agent.current_route[agent.route_index]
                if (agent.state == "COMMUTING" and agent.current_route)
                else agent.home_node
            )

            # Retrieve node coordinates
            node_data = self.model.network.g.nodes[node_id]
            lat, lon = node_data["lat"], node_data["lon"]

            r = int(np.clip((lat - lat_start) / 0.01, 0, GRID_ROWS - 1))
            c = int(np.clip((lon - lon_start) / 0.01, 0, GRID_COLS - 1))
            grid_data[r][c]["density"] += 1

        # 2. Map road segment congestions to grid bins
        for u, v, edge_data in self.model.network.g.edges(data=True):
            if edge_data.get("type") == "road":
                u_lat = self.model.network.g.nodes[u]["lat"]
                u_lon = self.model.network.g.nodes[u]["lon"]

                r = int(np.clip((u_lat - lat_start) / 0.01, 0, GRID_ROWS - 1))
                c = int(np.clip((u_lon - lon_start) / 0.01, 0, GRID_COLS - 1))

                flow = edge_data.get("flow", 0)
                capacity = edge_data.get("capacity", 100.0)
                congestion = flow / max(10.0, capacity)

                grid_data[r][c]["congestion_sum"] += congestion
                grid_data[r][c]["road_count"] += 1

        # 3. Build and return serializable GridCell list
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                cell_lat = lat_start + r * 0.01
                cell_lon = lon_start + c * 0.01
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
