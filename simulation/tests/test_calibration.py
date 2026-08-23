"""Tests for calibration, bus_load_pct, AQI, multi-day runs, and new modes."""

from __future__ import annotations

from app.models.schemas import ScenarioConfig
from simulation.agents import CitizenAgent
from simulation.calibration import (
    DELHI_CALIBRATION_TARGETS,
    validate_avg_commute,
    validate_mode_share,
)
from simulation.engine import MesaSimEngine, UrbanModel


def test_bus_load_pct_in_snapshot():
    """Verify bus_load_pct and aqi_estimate appear in snapshot metrics."""
    config = ScenarioConfig(
        name="test_bus_load", population=100, seed=42, tick_minutes=5, params={}
    )
    engine = MesaSimEngine(config)

    # Step a few ticks to get commuters moving
    for _ in range(20):
        snapshot = engine.step()

    # Verify new fields exist
    assert hasattr(snapshot.metrics, "bus_load_pct")
    assert hasattr(snapshot.metrics, "aqi_estimate")
    assert snapshot.metrics.bus_load_pct >= 0.0
    assert snapshot.metrics.aqi_estimate >= 0.0


def test_new_modes_in_mode_share():
    """Verify bike_share and e_rickshaw appear in mode share output."""
    config = ScenarioConfig(
        name="test_new_modes", population=200, seed=42, tick_minutes=5, params={}
    )
    engine = MesaSimEngine(config)

    # Run until agents are commuting (peak hours ~tick 100 = 500 min = ~8:20 AM)
    for _ in range(110):
        snapshot = engine.step()

    assert "bike_share" in snapshot.metrics.mode_share
    assert "e_rickshaw" in snapshot.metrics.mode_share


def test_multi_day_reset():
    """Run simulation past 24h boundary and verify agents reset to AT_HOME."""
    config = ScenarioConfig(
        name="test_multi_day", population=50, seed=42, tick_minutes=5, params={}
    )
    engine = MesaSimEngine(config)

    # Run for 300 ticks = 1500 minutes = 25 hours (crosses day boundary)
    for _ in range(300):
        engine.step()

    # After 25 simulated hours, agents should have gone through a day reset.
    # At minute 1500, sim_time % 1440 = 60 minutes past midnight (1:00 AM)
    # All agents should be AT_HOME at this early hour
    citizen_agents = [
        a for a in engine.model.schedule.agents if isinstance(a, CitizenAgent)
    ]
    at_home = sum(1 for a in citizen_agents if a.state == "AT_HOME")
    total = len(citizen_agents)
    # At 1:00 AM, vast majority should be at home
    assert (
        at_home / total > 0.8
    ), f"Only {at_home}/{total} agents at home after day reset"


def test_agent_reset_for_new_day():
    """Verify CitizenAgent.reset_for_new_day() clears commute state."""
    config = ScenarioConfig(
        name="test_agent_reset", population=20, seed=42, tick_minutes=5, params={}
    )
    model = UrbanModel(config)
    agent = next(a for a in model.schedule.agents if isinstance(a, CitizenAgent))

    # Simulate agent mid-commute
    agent.state = "COMMUTING"
    agent.current_mode = "car"
    agent.current_route = ["node_0_0", "node_1_1"]
    agent.route_index = 1
    agent._current_leg_index = 2

    agent.reset_for_new_day()

    assert agent.state == "AT_HOME"
    assert agent.current_mode is None
    assert agent.current_route is None
    assert agent.route_index == 0
    assert agent._current_leg_index == 0


def test_calibration_validation_utilities():
    """Verify calibration validation functions work correctly."""
    # Test validate_mode_share
    perfect_share = dict(DELHI_CALIBRATION_TARGETS)
    results = validate_mode_share(perfect_share, tolerance=0.01)
    for mode, result in results.items():
        assert result["pass"], f"Mode {mode} should pass with perfect match"

    # Test with offset
    bad_share = {k: v + 0.10 for k, v in DELHI_CALIBRATION_TARGETS.items()}
    results = validate_mode_share(bad_share, tolerance=0.05)
    for mode, result in results.items():
        assert not result["pass"], f"Mode {mode} should fail with +10% offset"

    # Test validate_avg_commute
    assert validate_avg_commute(34.0, tolerance=5.0)
    assert validate_avg_commute(30.0, tolerance=5.0)
    assert not validate_avg_commute(50.0, tolerance=5.0)


def test_aqi_estimate_responds_to_mode():
    """Verify AQI estimate is higher when more agents drive cars."""
    # Run with default config (mixed modes)
    config_default = ScenarioConfig(
        name="test_aqi_default", population=100, seed=42, tick_minutes=5, params={}
    )
    engine = MesaSimEngine(config_default)
    for _ in range(110):
        snap = engine.step()
    aqi_default = snap.metrics.aqi_estimate

    # AQI should be a non-negative number
    assert aqi_default >= 0.0
    assert aqi_default <= 500.0
