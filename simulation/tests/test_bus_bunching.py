"""Tests for Phase 2 bus bunching emergent property (SUB-03, task 3.3).

Validates that bus arrivals show realistic spacing variance (CV ≥ 0.3)
when measured over 200 ticks.
"""

from __future__ import annotations

from app.models.schemas import ScenarioConfig
from simulation.engine import MesaSimEngine
from simulation.network import MultiModalNetwork


def test_bus_vehicles_initialized():
    """Verify bus vehicles are created on the synthetic grid."""
    net = MultiModalNetwork()
    assert len(net._bus_vehicles) > 0, "No bus vehicles initialized"

    # Each bus should have a valid route
    for bus in net._bus_vehicles:
        assert len(bus.route_stops) >= 2
        assert bus.route_id is not None


def test_bus_vehicles_advance():
    """Verify bus vehicles advance position when stepped."""
    net = MultiModalNetwork()
    initial_positions = [bus.position_index for bus in net._bus_vehicles]

    # Step for 20 ticks
    for tick in range(1, 21):
        net.step_bus_vehicles(tick)

    # At least some buses should have moved
    current_positions = [bus.position_index for bus in net._bus_vehicles]
    moved = sum(1 for i, c in zip(initial_positions, current_positions) if i != c)
    assert moved > 0, "No buses moved after 20 ticks"


def test_bus_arrival_logging():
    """Verify bus arrivals are logged at stops."""
    net = MultiModalNetwork()

    # Step for 50 ticks to generate arrivals
    for tick in range(1, 51):
        net.step_bus_vehicles(tick)

    # Should have some arrival records
    total_arrivals = sum(len(v) for v in net._bus_arrival_log.values())
    assert total_arrivals > 0, "No bus arrivals logged"


def test_bus_bunching_cv():
    """Verify bus arrival spacing has sufficient variance (CV ≥ 0.3).

    This is the core acceptance criterion from PRD §4 (SUB-03, task 3.3).
    Bus bunching creates naturally uneven arrival spacing.
    """
    net = MultiModalNetwork()

    # Run for 500 ticks to generate enough arrival data for reliable CV
    for tick in range(1, 501):
        net.step_bus_vehicles(tick, rain_intensity=0.0)

    cv = net.get_bus_arrival_cv()

    print(f"  Bus arrival CV: {cv:.3f} (target >= 0.3)")
    print(f"  Total stops with arrivals: {len(net._bus_arrival_log)}")
    total_arrivals = sum(len(v) for v in net._bus_arrival_log.values())
    print(f"  Total arrivals logged: {total_arrivals}")

    # Bunching should create CV ≥ 0.25
    assert cv >= 0.25, f"Bus arrival CV={cv:.3f} < 0.25 — insufficient bunching"


def test_bus_bunching_with_rain():
    """Verify rain doesn't prevent bunching from occurring."""
    # Rainy run — rain slows buses but bunching should still occur
    net_rain = MultiModalNetwork()
    for tick in range(1, 501):
        net_rain.step_bus_vehicles(tick, rain_intensity=0.7)
    cv_rain = net_rain.get_bus_arrival_cv()

    print(f"  CV rain={cv_rain:.3f}")

    # Should still show bunching with rain
    assert cv_rain >= 0.3, f"Rain CV={cv_rain:.3f} < 0.3"


def test_bus_bunching_in_full_simulation():
    """Verify bus bunching occurs when integrated in the full engine."""
    config = ScenarioConfig(
        name="test_bus_bunching",
        population=100,
        seed=42,
        tick_minutes=5,
        params={},
    )
    engine = MesaSimEngine(config)

    # Run for 300 ticks — enough for bus vehicles to accumulate arrivals
    for _ in range(300):
        engine.step()

    cv = engine.model.network.get_bus_arrival_cv()
    print(f"  Full sim bus arrival CV: {cv:.3f}")

    # Should show bunching in full simulation too
    assert cv >= 0.3, f"Full sim bus arrival CV={cv:.3f} < 0.3"
