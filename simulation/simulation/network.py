"""Transportation & multi-modal network graph.

Represents roads, buses, and metro lines with routing and congestion capabilities.
"""

from __future__ import annotations

import math
from typing import TypedDict
import networkx as nx

# Central coordinates for Bengaluru-ish region
CITY_LAT = 12.9716
CITY_LON = 77.5946

# Default travel speed constants (meters per second)
WALK_SPEED = 1.4  # ~5 km/h
BIKE_SPEED = 4.2  # ~15 km/h
BUS_BASE_SPEED = 6.0  # ~22 km/h
METRO_SPEED = 12.0  # ~43 km/h
CAR_FREE_FLOW_SPEED = 11.0  # ~40 km/h


class SegmentInfo(TypedDict):
    length: float
    capacity: float
    free_flow_speed: float
    flow: int
    metro_line: str | None
    bus_route: str | None


class MultiModalNetwork:
    """Multi-modal transportation network (Roads, Metro, Bus).

    Maintains a physical NetworkX graph of roads and transit routes,
    updating dynamic travel times using a BPR congestion model.
    """

    def __init__(self, size: int = 8, spacing: float = 0.01) -> None:
        """Initialize the synthetic multi-modal Bengaluru grid.

        size: grid size (e.g. 8x8 intersections)
        spacing: coordinate distance between adjacent grid intersections (~1.1 km)
        """
        self.g = nx.DiGraph()
        self.size = size
        self.spacing = spacing

        # High-performance routing cache: (source, target, mode) -> path
        self._routing_cache: dict[tuple[str, str, str], list[str] | None] = {}

        # Track active policies & dynamic settings internally
        self._disabled_metro_lines: set[str] = set()
        self._bus_capacity_multiplier: float = 1.0
        self._fuel_price_delta_paise: int = 0
        self._weather_rain_intensity: float = 0.0

        # Build synthetic road intersections (Grid nodes)
        self._build_road_nodes()
        self._build_road_links()

        # Build Transit lines (Metro Purple and Green, major Bus loops)
        self._build_metro_system()
        self._build_bus_system()

    def clear_routing_cache(self) -> None:
        """Clear the routing cache when network conditions or parameters change."""
        self._routing_cache.clear()

    @property
    def disabled_metro_lines(self) -> set[str]:
        return self._disabled_metro_lines

    @disabled_metro_lines.setter
    def disabled_metro_lines(self, value: set[str]) -> None:
        self._disabled_metro_lines = value
        self.clear_routing_cache()

    @property
    def bus_capacity_multiplier(self) -> float:
        return self._bus_capacity_multiplier

    @bus_capacity_multiplier.setter
    def bus_capacity_multiplier(self, value: float) -> None:
        if self._bus_capacity_multiplier != value:
            self._bus_capacity_multiplier = value
            self.clear_routing_cache()

    @property
    def fuel_price_delta_paise(self) -> int:
        return self._fuel_price_delta_paise

    @fuel_price_delta_paise.setter
    def fuel_price_delta_paise(self, value: int) -> None:
        if self._fuel_price_delta_paise != value:
            self._fuel_price_delta_paise = value
            self.clear_routing_cache()

    @property
    def weather_rain_intensity(self) -> float:
        return self._weather_rain_intensity

    @weather_rain_intensity.setter
    def weather_rain_intensity(self, value: float) -> None:
        if self._weather_rain_intensity != value:
            self._weather_rain_intensity = value
            self.clear_routing_cache()

        # Build synthetic road intersections (Grid nodes)
        self._build_road_nodes()
        self._build_road_links()

        # Build Transit lines (Metro Purple and Green, major Bus loops)
        self._build_metro_system()
        self._build_bus_system()

    def _build_road_nodes(self) -> None:
        """Create road intersection nodes centered on the city."""
        lat_start = CITY_LAT - (self.size / 2) * self.spacing
        lon_start = CITY_LON - (self.size / 2) * self.spacing

        for r in range(self.size):
            for c in range(self.size):
                node_id = f"node_{r}_{c}"
                lat = lat_start + r * self.spacing
                lon = lon_start + c * self.spacing
                self.g.add_node(
                    node_id, type="intersection", lat=lat, lon=lon, r=r, c=c
                )

    def _build_road_links(self) -> None:
        """Connect intersections with directed grid links (roads)."""
        for r in range(self.size):
            for c in range(self.size):
                curr = f"node_{r}_{c}"

                # Connect horizontally and vertically
                neighbors = []
                if r > 0:
                    neighbors.append(f"node_{r-1}_{c}")
                if r < self.size - 1:
                    neighbors.append(f"node_{r+1}_{c}")
                if c > 0:
                    neighbors.append(f"node_{r}_{c-1}")
                if c < self.size - 1:
                    neighbors.append(f"node_{r}_{c+1}")

                for nbr in neighbors:
                    # Physical distance in meters (approx. 111,000 meters per degree)
                    dx = (
                        (self.g.nodes[nbr]["lon"] - self.g.nodes[curr]["lon"])
                        * 111000
                        * math.cos(math.radians(CITY_LAT))
                    )
                    dy = (self.g.nodes[nbr]["lat"] - self.g.nodes[curr]["lat"]) * 111000
                    length = math.sqrt(dx * dx + dy * dy)

                    # Lanes capacity: segments closer to center have higher capacity
                    dist_to_center = math.sqrt(
                        (r - self.size / 2) ** 2 + (c - self.size / 2) ** 2
                    )
                    capacity = max(100.0, 500.0 - 40.0 * dist_to_center)

                    self.g.add_edge(
                        curr,
                        nbr,
                        type="road",
                        length=length,
                        capacity=capacity,
                        flow=0,
                        free_flow_speed=CAR_FREE_FLOW_SPEED,
                        metro_line=None,
                        bus_route=None,
                    )

    def _build_metro_system(self) -> None:
        """Create Purple and Green metro lines cutting through the grid."""
        # Purple Line: Horizontal cut across the middle row
        purple_r = self.size // 2
        purple_nodes = [f"node_{purple_r}_{c}" for c in range(self.size)]
        self._wire_metro_line("purple", purple_nodes)

        # Green Line: Vertical cut across the middle column
        green_c = self.size // 2
        green_nodes = [f"node_{r}_{green_c}" for r in range(self.size)]
        self._wire_metro_line("green", green_nodes)

    def _wire_metro_line(self, line_name: str, nodes: list[str]) -> None:
        """Create dedicated metro station nodes, walk-to-transit transfer links, and metro tracks."""
        station_ids = []
        for n in nodes:
            lat = self.g.nodes[n]["lat"]
            lon = self.g.nodes[n]["lon"]
            station_id = f"metro_{line_name}_station_{n}"
            station_ids.append(station_id)

            # Add dedicated metro station node
            self.g.add_node(
                station_id, type="metro_station", line=line_name, lat=lat, lon=lon
            )
            # Mark the physical road intersection as having transit access
            self.g.nodes[n]["metro_station"] = True

            # Add bidirectional transfer edges (50-meter walking link to/from platforms)
            self.g.add_edge(
                n,
                station_id,
                type="transfer",
                length=50.0,
                capacity=1e9,
                flow=0,
                free_flow_speed=WALK_SPEED,
                metro_line=None,
                bus_route=None,
            )
            self.g.add_edge(
                station_id,
                n,
                type="transfer",
                length=50.0,
                capacity=1e9,
                flow=0,
                free_flow_speed=WALK_SPEED,
                metro_line=None,
                bus_route=None,
            )

        # Wire metro tracks between consecutive stations
        for i in range(len(station_ids) - 1):
            s1, s2 = station_ids[i], station_ids[i + 1]

            # Add bidirectional metro links (completely separate from road links)
            for src, dst in [(s1, s2), (s2, s1)]:
                # Physical length matching road segment
                dx = (
                    (self.g.nodes[dst]["lon"] - self.g.nodes[src]["lon"])
                    * 111000
                    * math.cos(math.radians(CITY_LAT))
                )
                dy = (self.g.nodes[dst]["lat"] - self.g.nodes[src]["lat"]) * 111000
                length = math.sqrt(dx * dx + dy * dy)

                self.g.add_edge(
                    src,
                    dst,
                    type="metro",
                    line=line_name,
                    length=length,
                    capacity=10000.0,  # massive capacity
                    flow=0,
                    free_flow_speed=METRO_SPEED,
                    metro_line=line_name,
                    bus_route=None,
                )

    def _build_bus_system(self) -> None:
        """Build major bus loop lines."""
        # Bus loop around the inner square (e.g., ring road)
        # For a size=8 grid, loop around index 2 and 5
        bus_nodes = [
            "node_2_2",
            "node_2_3",
            "node_2_4",
            "node_2_5",
            "node_3_5",
            "node_4_5",
            "node_5_5",
            "node_5_4",
            "node_5_3",
            "node_5_2",
            "node_4_2",
            "node_3_2",
            "node_2_2",
        ]

        for i in range(len(bus_nodes) - 1):
            n1, n2 = bus_nodes[i], bus_nodes[i + 1]
            self.g.nodes[n1]["bus_stop"] = True
            self.g.nodes[n2]["bus_stop"] = True

            # Add dynamic bus segment tag to existing road edges or new ones
            for src, dst in [(n1, n2), (n2, n1)]:
                if self.g.has_edge(src, dst):
                    self.g.edges[src, dst]["bus_route"] = "ring_road"

    def get_nearest_node(self, lat: float, lon: float) -> str:
        """Find the nearest road intersection node to a given lat/lon."""
        best_node = None
        min_dist = float("inf")

        for node_id, data in self.g.nodes(data=True):
            if data.get("type") == "intersection":
                d_lat = data["lat"] - lat
                d_lon = data["lon"] - lon
                dist = d_lat * d_lat + d_lon * d_lon
                if dist < min_dist:
                    min_dist = dist
                    best_node = node_id

        return best_node or "node_0_0"

    def compute_bpr_travel_time(self, u: str, v: str, edge_data: dict) -> float:
        """Compute travel time (seconds) on an edge using BPR congestion formula."""
        length = edge_data["length"]
        free_flow_speed = edge_data["free_flow_speed"]
        edge_type = edge_data["type"]

        # Base travel time in seconds
        t_zero = length / free_flow_speed

        if edge_type == "road":
            # Apply weather speed reduction
            # Rain drops car speed by up to 40%
            weather_mult = 1.0 - 0.40 * self.weather_rain_intensity
            speed = free_flow_speed * weather_mult
            t_zero = length / max(1.0, speed)

            # Bureau of Public Roads (BPR) formula
            flow = edge_data["flow"]
            capacity = edge_data["capacity"]
            # Weather reduces lane capacity too by up to 30%
            cap = capacity * (1.0 - 0.30 * self.weather_rain_intensity)

            # Calibrated mixed-traffic BPR formula for Indian roads
            # Mixed-traffic has lower threshold of speed degradation but standard exponential growth
            # We use alpha = 0.20 and beta = 4.0 to make it slightly more sensitive to early traffic (mixed-traffic friction)
            alpha = 0.20
            beta = 4.0
            congestion_term = alpha * ((flow / max(10.0, cap)) ** beta)
            # Cap congestion multiplier to 9.0 to prevent infinite delay spikes
            congestion_term = min(9.0, congestion_term)
            return t_zero * (1.0 + congestion_term)

        elif edge_type == "metro":
            line = edge_data["line"]
            if line in self.disabled_metro_lines:
                return 1e9  # impassable!
            return t_zero

        elif edge_type == "transfer":
            return length / WALK_SPEED

        elif edge_type == "bus":
            return t_zero

        return t_zero

    def find_shortest_path(
        self, source: str, target: str, mode: str
    ) -> list[str] | None:
        """Find the shortest path for a given mode of transport using the routing cache.

        Returns a list of node IDs or None.
        """
        if source == target:
            return [source]

        # Check in high-performance cache
        cache_key = (source, target, mode)
        if cache_key in self._routing_cache:
            return self._routing_cache[cache_key]

        # Define edge weight mapping based on the travel mode
        def weight_func(u: str, v: str, edge_attr: dict) -> float:
            etype = edge_attr["type"]

            if mode == "walk":
                # Walking uses road network only at walk speed
                if etype != "road":
                    return 1e9
                return edge_attr["length"] / WALK_SPEED

            elif mode == "bike":
                # Biking uses road network only at bike speed, with minor rain penalty
                if etype != "road":
                    return 1e9
                rain_penalty = 1.0 + 0.5 * self.weather_rain_intensity
                return (edge_attr["length"] / BIKE_SPEED) * rain_penalty

            elif mode in ("car", "auto"):
                # Cars and autos use road networks and are subject to congestion
                if etype != "road":
                    return 1e9
                return self.compute_bpr_travel_time(u, v, edge_attr)

            elif mode == "metro":
                # Metro routes can travel on metro links (fast), transfer walking edges, and walk along roads (slow) to transfer
                if etype == "metro":
                    line = edge_attr["line"]
                    if line in self.disabled_metro_lines:
                        return 1e9
                    return edge_attr["length"] / METRO_SPEED
                elif etype == "transfer":
                    return edge_attr["length"] / WALK_SPEED
                elif etype == "road":
                    # Walking to transfer
                    return edge_attr["length"] / WALK_SPEED
                return 1e9

            elif mode == "bus":
                # Buses travel along roads. If edge has a bus line tag, it's cheap (transit speed)
                # Else they walk to connect (transfer)
                if etype == "road":
                    if edge_attr.get("bus_route"):
                        # Travel by bus
                        return edge_attr["length"] / BUS_BASE_SPEED
                    else:
                        # Walk
                        return edge_attr["length"] / WALK_SPEED
                return 1e9

            return 1e9

        try:
            path = nx.dijkstra_path(self.g, source, target, weight=weight_func)
            self._routing_cache[cache_key] = path
            return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            self._routing_cache[cache_key] = None
            return None

    def calculate_path_travel_time(self, path: list[str], mode: str) -> float:
        """Sum travel times over a path for a specific mode."""
        if not path or len(path) < 2:
            return 0.0

        total_time = 0.0
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            if self.g.has_edge(u, v):
                edge_data = self.g.edges[u, v]

                # Define weight
                etype = edge_data["type"]
                if mode == "walk":
                    t = edge_data["length"] / WALK_SPEED
                elif mode == "bike":
                    t = (edge_data["length"] / BIKE_SPEED) * (
                        1.0 + 0.5 * self.weather_rain_intensity
                    )
                elif mode in ("car", "auto"):
                    t = self.compute_bpr_travel_time(u, v, edge_data)
                elif mode == "metro":
                    if etype == "metro":
                        t = edge_data["length"] / METRO_SPEED
                    elif etype == "transfer":
                        t = edge_data["length"] / WALK_SPEED
                    else:
                        t = edge_data["length"] / WALK_SPEED
                elif mode == "bus":
                    if etype == "road" and edge_data.get("bus_route"):
                        t = edge_data["length"] / BUS_BASE_SPEED
                    else:
                        t = edge_data["length"] / WALK_SPEED
                else:
                    t = edge_data["length"] / WALK_SPEED

                total_time += t
            else:
                # Fallback if graph is missing edge
                total_time += 10.0
        return total_time / 60.0  # return minutes

    def update_road_congestion(self, active_commuters: list) -> None:
        """Reset flow and count active agents on each road segment, and invalidate the routing cache."""
        # Reset edge flows
        for u, v in self.g.edges:
            self.g.edges[u, v]["flow"] = 0

        # Increment flows for agents currently on road segments
        for agent in active_commuters:
            if agent.current_route and agent.route_index < len(agent.current_route) - 1:
                idx = agent.route_index
                u = agent.current_route[idx]
                v = agent.current_route[idx + 1]
                if self.g.has_edge(u, v) and self.g.edges[u, v]["type"] == "road":
                    self.g.edges[u, v]["flow"] += 1

        # Clear routing cache as congestion and travel times have changed for the next tick
        self.clear_routing_cache()
