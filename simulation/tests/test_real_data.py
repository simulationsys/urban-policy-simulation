"""Tests for real OSM data loading and simulation.

These tests verify that the MultiModalNetwork can load real OSM GraphML data,
overlay metro/bus transit, and run a full simulation cycle.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from simulation.network import MultiModalNetwork

# Resolve data paths relative to the project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DATA_DIR = _PROJECT_ROOT / "data" / "processed_data"
_GRAPHML = _DATA_DIR / "network.graphml"
_METRO_JSON = _DATA_DIR / "metro_network.json"
_BUS_JSON = _DATA_DIR / "bus_routes.json"

# Skip all tests in this module if the GraphML file is missing
pytestmark = pytest.mark.skipif(
    not _GRAPHML.exists(),
    reason=f"Real data not available: {_GRAPHML}",
)


class TestOSMNetworkLoading:
    """Tests for loading real OSM road network."""

    def test_load_graphml_basic(self):
        """Verify GraphML loads and produces a populated graph."""
        net = MultiModalNetwork.load_from_osm(str(_GRAPHML))
        assert net._is_real_data is True
        assert net.g.number_of_nodes() > 1000
        assert net.g.number_of_edges() > 3000

    def test_node_attributes(self):
        """Verify nodes have required attributes (type, lat, lon)."""
        net = MultiModalNetwork.load_from_osm(str(_GRAPHML))
        intersection_nodes = [
            n for n, d in net.g.nodes(data=True) if d.get("type") == "intersection"
        ]
        assert len(intersection_nodes) > 1000

        # Check a sample node
        sample = intersection_nodes[0]
        data = net.g.nodes[sample]
        assert data["type"] == "intersection"
        assert 28.0 < data["lat"] < 29.0  # Delhi latitude range
        assert 77.0 < data["lon"] < 78.0  # Delhi longitude range

    def test_edge_attributes(self):
        """Verify edges have required attributes for BPR model."""
        net = MultiModalNetwork.load_from_osm(str(_GRAPHML))
        road_edges = [
            (u, v, d) for u, v, d in net.g.edges(data=True) if d.get("type") == "road"
        ]
        assert len(road_edges) > 3000

        # Check a sample edge
        _u, _v, data = road_edges[0]
        assert data["type"] == "road"
        assert data["length"] > 0
        assert data["capacity"] > 0
        assert data["free_flow_speed"] > 0
        assert data["flow"] == 0
        assert "metro_line" in data
        assert "bus_route" in data

    def test_bounding_box(self):
        """Verify bounding box covers the Rajiv Chowk area."""
        net = MultiModalNetwork.load_from_osm(str(_GRAPHML))
        # Rajiv Chowk is at ~28.6328, 77.2197
        assert net.lat_min < 28.6328 < net.lat_max
        assert net.lon_min < 77.2197 < net.lon_max

    def test_get_nearest_node(self):
        """Verify nearest-node lookup works with real OSM IDs."""
        net = MultiModalNetwork.load_from_osm(str(_GRAPHML))

        # Find nearest to Rajiv Chowk
        node = net.get_nearest_node(28.6328, 77.2197)
        assert node is not None
        data = net.g.nodes[node]
        assert data["type"] == "intersection"
        # Should be within ~500m
        assert abs(data["lat"] - 28.6328) < 0.005
        assert abs(data["lon"] - 77.2197) < 0.005

    def test_get_intersection_nodes(self):
        """Verify helper returns all intersection nodes."""
        net = MultiModalNetwork.load_from_osm(str(_GRAPHML))
        nodes = net.get_intersection_nodes()
        assert len(nodes) > 1000
        # All should be strings
        assert all(isinstance(n, str) for n in nodes)


class TestRealDataRouting:
    """Tests for routing on the real OSM graph."""

    def test_car_routing(self):
        """Verify car routing works between two real nodes."""
        net = MultiModalNetwork.load_from_osm(str(_GRAPHML))

        # Pick two nodes that are far apart
        node_a = net.get_nearest_node(28.61, 77.20)
        node_b = net.get_nearest_node(28.65, 77.24)

        path = net.find_shortest_path(node_a, node_b, "car")
        assert path is not None
        assert len(path) > 2
        assert path[0] == node_a
        assert path[-1] == node_b

    def test_walk_routing(self):
        """Verify walking route exists between nearby nodes."""
        net = MultiModalNetwork.load_from_osm(str(_GRAPHML))

        node_a = net.get_nearest_node(28.632, 77.219)
        node_b = net.get_nearest_node(28.634, 77.221)

        path = net.find_shortest_path(node_a, node_b, "walk")
        assert path is not None

    def test_travel_time_reasonable(self):
        """Verify travel times are in a reasonable range."""
        net = MultiModalNetwork.load_from_osm(str(_GRAPHML))

        node_a = net.get_nearest_node(28.62, 77.21)
        node_b = net.get_nearest_node(28.64, 77.23)

        path = net.find_shortest_path(node_a, node_b, "car")
        assert path is not None

        travel_time = net.calculate_path_travel_time(path, "car")
        # ~3km trip should take 5-30 minutes by car
        assert 2.0 < travel_time < 60.0

    def test_routing_cache_works(self):
        """Verify routing cache populates and invalidates."""
        net = MultiModalNetwork.load_from_osm(str(_GRAPHML))

        node_a = net.get_nearest_node(28.632, 77.219)
        node_b = net.get_nearest_node(28.635, 77.222)

        assert len(net._routing_cache) == 0
        net.find_shortest_path(node_a, node_b, "car")
        assert len(net._routing_cache) == 1

        # Invalidate
        net.weather_rain_intensity = 0.5
        assert len(net._routing_cache) == 0


@pytest.mark.skipif(
    not _METRO_JSON.exists(),
    reason=f"Metro data not available: {_METRO_JSON}",
)
class TestMetroOverlay:
    """Tests for metro line overlay on real graph."""

    def test_metro_stations_created(self):
        """Verify metro station nodes are created."""
        net = MultiModalNetwork.load_from_osm(
            str(_GRAPHML), metro_json_path=str(_METRO_JSON)
        )

        station_nodes = [
            n for n, d in net.g.nodes(data=True) if d.get("type") == "metro_station"
        ]
        # We only have a 5-station stub in JSON (yielding 6 metro nodes since Rajiv Chowk is an interchange)
        assert len(station_nodes) >= 5

    def test_metro_transfers_exist(self):
        """Verify transfer edges connect stations to road nodes."""
        net = MultiModalNetwork.load_from_osm(
            str(_GRAPHML), metro_json_path=str(_METRO_JSON)
        )

        transfer_edges = [
            (u, v) for u, v, d in net.g.edges(data=True) if d.get("type") == "transfer"
        ]
        assert len(transfer_edges) >= 10  # 5 stations * 2 directions

    def test_metro_tracks_exist(self):
        """Verify metro track edges connect consecutive stations."""
        net = MultiModalNetwork.load_from_osm(
            str(_GRAPHML), metro_json_path=str(_METRO_JSON)
        )

        metro_edges = [
            (u, v, d) for u, v, d in net.g.edges(data=True) if d.get("type") == "metro"
        ]
        # 2 segments per line × 2 lines × 2 directions = 8
        assert len(metro_edges) >= 8

    def test_metro_routing(self):
        """Verify routing via metro between two distant points."""
        net = MultiModalNetwork.load_from_osm(
            str(_GRAPHML), metro_json_path=str(_METRO_JSON)
        )

        # Near a Yellow Line station (north) to near a Yellow Line station (south)
        node_a = net.get_nearest_node(28.643, 77.222)  # Near New Delhi
        node_b = net.get_nearest_node(28.623, 77.214)  # Near Patel Chowk

        path = net.find_shortest_path(node_a, node_b, "metro")
        assert path is not None

        # Path should include metro station nodes
        has_metro_node = any("metro_" in str(n) for n in path)
        assert has_metro_node


@pytest.mark.skipif(
    not _BUS_JSON.exists(),
    reason=f"Bus data not available: {_BUS_JSON}",
)
class TestBusOverlay:
    """Tests for bus route overlay on real graph."""

    def test_bus_routes_tagged(self):
        """Verify road edges are tagged with bus route IDs."""
        net = MultiModalNetwork.load_from_osm(
            str(_GRAPHML),
            metro_json_path=str(_METRO_JSON),
            bus_json_path=str(_BUS_JSON),
        )

        bus_edges = [
            (u, v, d)
            for u, v, d in net.g.edges(data=True)
            if d.get("bus_route") is not None
        ]
        assert len(bus_edges) > 0

    def test_bus_stops_marked(self):
        """Verify bus stop nodes are tagged."""
        net = MultiModalNetwork.load_from_osm(
            str(_GRAPHML),
            metro_json_path=str(_METRO_JSON),
            bus_json_path=str(_BUS_JSON),
        )

        bus_stop_nodes = [
            n for n, d in net.g.nodes(data=True) if d.get("bus_stop") is True
        ]
        assert len(bus_stop_nodes) > 5


class TestFullIntegration:
    """Full integration: create UrbanModel with real data and step."""

    def test_urban_model_real_data(self):
        """Verify UrbanModel initializes and steps with real OSM data."""
        from app.models.schemas import ScenarioConfig
        from simulation.engine import UrbanModel

        config = ScenarioConfig(
            name="test_real_delhi",
            population=50,  # Small population for speed
            seed=42,
            tick_minutes=5,
            use_real_data=True,
            network_paths={
                "graphml": str(_GRAPHML),
                "metro_json": str(_METRO_JSON) if _METRO_JSON.exists() else "",
                "bus_json": str(_BUS_JSON) if _BUS_JSON.exists() else "",
            },
        )
        model = UrbanModel(config)

        # Verify agents are assigned to real OSM node IDs (strings)
        from simulation.agents import CitizenAgent

        citizen_agents = [
            a for a in model.schedule.agents if isinstance(a, CitizenAgent)
        ]
        assert len(citizen_agents) == 50
        for agent in citizen_agents:
            assert agent.home_node in model.network.g.nodes
            node_data = model.network.g.nodes[agent.home_node]
            assert 28.0 < node_data["lat"] < 29.0

        # Step 5 ticks
        model.step()
        model.step()
        model.step()
        model.step()
        model.step()

    def test_engine_real_data_snapshot(self):
        """Verify MesaSimEngine produces valid snapshots with real data."""
        from app.models.schemas import ScenarioConfig
        from simulation.engine import MesaSimEngine

        config = ScenarioConfig(
            name="test_real_snapshot",
            population=30,
            seed=42,
            tick_minutes=5,
            use_real_data=True,
            network_paths={
                "graphml": str(_GRAPHML),
                "metro_json": str(_METRO_JSON) if _METRO_JSON.exists() else "",
                "bus_json": str(_BUS_JSON) if _BUS_JSON.exists() else "",
            },
        )
        engine = MesaSimEngine(config)

        snapshot = engine.step()
        assert snapshot.tick == 1
        assert len(snapshot.grid) == 100  # 10×10

        # Grid cells should have real Delhi coordinates
        lats = [c.lat for c in snapshot.grid]
        lons = [c.lon for c in snapshot.grid]
        assert min(lats) > 28.0
        assert max(lats) < 29.0
        assert min(lons) > 77.0
        assert max(lons) < 78.0
