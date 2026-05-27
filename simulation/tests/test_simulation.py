"""Unit and integration tests for the Mesa Simulation Core."""

from __future__ import annotations

import pytest
from app.models.schemas import ScenarioConfig, Event, EventType
from simulation.engine import MesaSimEngine, UrbanModel


def test_model_initialization():
    """Verify the UrbanModel correctly initializes its agents and multi-modal network."""
    config = ScenarioConfig(
        name="test_scenario",
        population=100,
        seed=42,
        tick_minutes=5,
        params={}
    )
    model = UrbanModel(config)

    # Assert model parameters
    assert len(model.schedule.agents) == 100
    assert model.current_tick == 0
    assert model.sim_time_minutes == 0

    # Assert spatial network was created
    assert len(model.network.g.nodes) > 0
    assert len(model.network.g.edges) > 0

    # Assert agent details are correct
    for agent in model.schedule.agents:
        assert 1 <= agent.income_bracket <= 5
        assert 18 <= agent.age <= 70
        assert agent.home_node != agent.work_node


def test_sim_engine_steps():
    """Verify advancing ticks using MesaSimEngine correct increments states."""
    config = ScenarioConfig(
        name="test_scenario",
        population=100,
        seed=42,
        tick_minutes=5,
        params={}
    )
    engine = MesaSimEngine(config)

    assert engine.current_tick == 0

    # Step 1 tick
    snapshot = engine.step()
    assert engine.current_tick == 1
    assert snapshot.tick == 1
    assert snapshot.sim_time_minutes == 5
    assert len(snapshot.grid) == 64  # 8x8 coarse grid
    assert snapshot.metrics.tick == 1


def test_event_injection():
    """Verify events propagate and update physical properties of network."""
    config = ScenarioConfig(
        name="test_scenario",
        population=100,
        seed=42,
        tick_minutes=5,
        params={}
    )
    engine = MesaSimEngine(config)

    assert engine.model.network.weather_rain_intensity == 0.0

    # Queue weather event
    ev = Event(
        type=EventType.weather,
        payload={"rain_intensity": 0.85}
    )
    engine.queue_event(ev)

    # Edge-flow before step should be unmodified
    assert engine.model.network.weather_rain_intensity == 0.0

    # Step 1 tick
    engine.step()

    # Verify event was dispatched
    assert engine.model.network.weather_rain_intensity == 0.85
    # Aggregated metric should match too
    assert engine.model.metrics.rain_intensity == 0.85


def test_strict_determinism():
    """Verify scenario config + seed reproduces identical run twice, byte-for-byte."""
    config_a = ScenarioConfig(
        name="deterministic_scenario",
        population=150,
        seed=101,
        tick_minutes=5,
        params={"bus_capacity_pct": 1.0}
    )
    config_b = ScenarioConfig(
        name="deterministic_scenario",
        population=150,
        seed=101,
        tick_minutes=5,
        params={"bus_capacity_pct": 1.0}
    )

    engine_a = MesaSimEngine(config_a)
    engine_b = MesaSimEngine(config_b)

    # Queue identical events
    ev_a = Event(type=EventType.weather, payload={"rain_intensity": 0.5})
    ev_b = Event(type=EventType.weather, payload={"rain_intensity": 0.5})
    engine_a.queue_event(ev_a)
    engine_b.queue_event(ev_b)

    # Run both engines for 20 ticks
    for _ in range(20):
        snap_a = engine_a.step()
        snap_b = engine_b.step()

        # Check metrics equality
        assert snap_a.metrics.tick == snap_b.metrics.tick
        assert snap_a.metrics.sim_time_minutes == snap_b.metrics.sim_time_minutes
        assert snap_a.metrics.rain_intensity == snap_b.metrics.rain_intensity
        assert snap_a.metrics.avg_commute_minutes == snap_b.metrics.avg_commute_minutes
        assert snap_a.metrics.metro_load_pct == snap_b.metrics.metro_load_pct
        assert snap_a.metrics.road_congestion_index == snap_b.metrics.road_congestion_index
        assert snap_a.metrics.agents_commuting == snap_b.metrics.agents_commuting
        
        # Check mode share matches perfectly
        for mode, val in snap_a.metrics.mode_share.items():
            assert snap_b.metrics.mode_share[mode] == val

        # Check grid cell matches perfectly
        for c1, c2 in zip(snap_a.grid, snap_b.grid):
            assert c1.lat == c2.lat
            assert c1.lon == c2.lon
            assert c1.density == c2.density
            assert c1.congestion == c2.congestion


def test_shortest_path_cache_and_invalidation():
    """Verify that routing cache saves redundant runs and invalidates on changes."""
    config = ScenarioConfig(
        name="test_scenario",
        population=10,
        seed=42,
        tick_minutes=5,
        params={}
    )
    model = UrbanModel(config)
    net = model.network

    source = "node_0_0"
    target = "node_5_5"
    
    # Check cache is initially empty
    assert len(net._routing_cache) == 0

    # First query - populates cache
    path1 = net.find_shortest_path(source, target, "car")
    assert path1 is not None
    assert len(net._routing_cache) == 1

    # Second query - retrieves from cache
    path2 = net.find_shortest_path(source, target, "car")
    assert path1 == path2

    # Invalidate cache via weather setter
    net.weather_rain_intensity = 0.5
    assert len(net._routing_cache) == 0

    # Query again and verify cache repopulated
    path3 = net.find_shortest_path(source, target, "car")
    assert len(net._routing_cache) == 1

    # Invalidate via congestion update
    net.update_road_congestion([])
    assert len(net._routing_cache) == 0


def test_multimodal_routing_and_transfers():
    """Verify separate metro station nodes and transfer edges route correctly."""
    import math
    config = ScenarioConfig(
        name="test_scenario",
        population=10,
        seed=42,
        tick_minutes=5,
        params={}
    )
    model = UrbanModel(config)
    net = model.network

    # Query metro route along horizontal purple line (runs along row 4)
    # Start near intersection node_4_0 and go to node_4_7
    source = "node_4_0"
    target = "node_4_7"

    path = net.find_shortest_path(source, target, "metro")
    assert path is not None
    
    # Path should include transfer node and metro station nodes, e.g.:
    # node_4_0 -> metro_purple_station_node_4_0 -> ... -> metro_purple_station_node_4_7 -> node_4_7
    assert any("metro_purple_station" in node for node in path)
    assert any(net.g.edges[path[i], path[i+1]]["type"] == "transfer" for i in range(len(path)-1))

    # Cars and autos should not use metro or transfer links
    car_path = net.find_shortest_path(source, target, "car")
    assert car_path is not None
    for i in range(len(car_path)-1):
        edge_data = net.g.edges[car_path[i], car_path[i+1]]
        assert edge_data["type"] == "road"


def test_calibrated_bpr_congestion():
    """Verify road travel times scale correctly with flow and mixed-traffic parameters."""
    import math
    config = ScenarioConfig(
        name="test_scenario",
        population=10,
        seed=42,
        tick_minutes=5,
        params={}
    )
    model = UrbanModel(config)
    net = model.network

    # Grab a road edge
    road_edges = [(u, v, d) for u, v, d in net.g.edges(data=True) if d["type"] == "road"]
    u, v, data = road_edges[0]

    # Free flow travel time
    t0 = net.compute_bpr_travel_time(u, v, data)

    # Congested travel time at capacity
    data_congested = data.copy()
    data_congested["flow"] = data["capacity"]
    t_congested = net.compute_bpr_travel_time(u, v, data_congested)

    # With mixed-traffic BPR, travel time at capacity should be exactly 1 + alpha = 1.20x free flow time
    assert math.isclose(t_congested, t0 * 1.20, rel_tol=1e-4)

    # Travel time should never spike infinitely (capped multiplier)
    data_overloaded = data.copy()
    data_overloaded["flow"] = int(data["capacity"] * 100) # 100x capacity!
    t_overloaded = net.compute_bpr_travel_time(u, v, data_overloaded)
    assert t_overloaded <= t0 * 10.0

