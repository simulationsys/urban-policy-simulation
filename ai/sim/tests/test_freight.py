"""Tests for heavy freight driver dataclasses and state machine."""

from __future__ import annotations

import pytest

from sim.agents.freight import FreightDriver, FreightOrder, FreightState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_driver(depot: int = 0, location: int = 0) -> FreightDriver:
    return FreightDriver(id=1, depot_node=depot, current_location=location)


def make_order(pickup: int = 10, delivery: int = 20, weight: float = 5.0) -> FreightOrder:
    return FreightOrder(order_id=1, pickup_node=pickup, delivery_node=delivery, weight_tonnes=weight)


# ---------------------------------------------------------------------------
# FreightOrder tests
# ---------------------------------------------------------------------------

def test_freight_order_defaults() -> None:
    """Order has sensible defaults."""
    order = make_order()
    assert order.priority == 1
    assert order.deadline_min == 24 * 60


# ---------------------------------------------------------------------------
# FreightDriver: basic properties
# ---------------------------------------------------------------------------

def test_initial_state_is_idle() -> None:
    driver = make_driver()
    assert driver.state == FreightState.IDLE


def test_available_capacity_full() -> None:
    driver = make_driver()
    assert driver.available_capacity == pytest.approx(driver.vehicle_capacity_tonnes)


def test_available_capacity_partially_loaded() -> None:
    driver = make_driver()
    driver.current_load_tonnes = 4.0
    assert driver.available_capacity == pytest.approx(6.0)


# ---------------------------------------------------------------------------
# Restricted hours
# ---------------------------------------------------------------------------

def test_can_operate_outside_restriction() -> None:
    """Driver can operate at noon (outside 7–11 AM restriction)."""
    driver = make_driver()
    assert driver.can_operate(12) is True


def test_restricted_during_peak_hours() -> None:
    """Driver is blocked during 7–11 AM (Delhi regulation)."""
    driver = make_driver()
    for hour in (7, 8, 9, 10):
        assert driver.can_operate(hour) is False


def test_allowed_at_restriction_boundary() -> None:
    """Hour 11 is the first hour outside the 7–11 ban."""
    driver = make_driver()
    assert driver.can_operate(11) is True
    assert driver.can_operate(6) is True


# ---------------------------------------------------------------------------
# assign_order
# ---------------------------------------------------------------------------

def test_assign_order_transitions_to_en_route_pickup() -> None:
    driver = make_driver()
    order = make_order(pickup=10, delivery=20, weight=5.0)
    driver.assign_order(order)
    assert driver.state == FreightState.EN_ROUTE_PICKUP
    assert driver.current_order is order


def test_assign_order_fails_if_not_idle() -> None:
    driver = make_driver()
    order = make_order()
    driver.assign_order(order)  # First assignment → EN_ROUTE_PICKUP
    second_order = FreightOrder(order_id=2, pickup_node=30, delivery_node=40, weight_tonnes=2.0)
    with pytest.raises(RuntimeError, match="Cannot assign order"):
        driver.assign_order(second_order)


def test_assign_order_fails_if_overweight() -> None:
    driver = FreightDriver(id=1, depot_node=0, current_location=0, vehicle_capacity_tonnes=5.0)
    order = FreightOrder(order_id=1, pickup_node=10, delivery_node=20, weight_tonnes=6.0)
    with pytest.raises(ValueError, match="exceeds available capacity"):
        driver.assign_order(order)


# ---------------------------------------------------------------------------
# State machine: full lifecycle
# ---------------------------------------------------------------------------

def test_full_state_machine_cycle() -> None:
    """IDLE → EN_ROUTE_PICKUP → LOADING → EN_ROUTE_DELIVERY → UNLOADING → RETURNING → IDLE."""
    driver = FreightDriver(id=1, depot_node=0, current_location=0)
    order = FreightOrder(order_id=1, pickup_node=10, delivery_node=20, weight_tonnes=3.0)

    # 1. Assign order
    driver.assign_order(order)
    assert driver.state == FreightState.EN_ROUTE_PICKUP

    # 2. Arrive at pickup
    driver.current_location = 10
    driver.step(current_hour=12)
    assert driver.state == FreightState.LOADING
    assert driver.current_load_tonnes == pytest.approx(3.0)

    # 3. Loading tick → depart for delivery
    driver.step(current_hour=12)
    assert driver.state == FreightState.EN_ROUTE_DELIVERY

    # 4. Arrive at delivery
    driver.current_location = 20
    driver.step(current_hour=12)
    assert driver.state == FreightState.UNLOADING

    # 5. Unloading tick → return to depot
    driver.step(current_hour=12)
    assert driver.state == FreightState.RETURNING
    assert driver.current_load_tonnes == pytest.approx(0.0)
    assert driver.completed_orders == 1
    assert driver.current_order is None

    # 6. Arrive at depot → IDLE
    driver.current_location = 0
    driver.step(current_hour=12)
    assert driver.state == FreightState.IDLE


def test_state_machine_pauses_during_restriction() -> None:
    """Driver in EN_ROUTE_DELIVERY does not transition during 7–11 AM ban."""
    driver = FreightDriver(id=1, depot_node=0, current_location=0)
    order = FreightOrder(order_id=1, pickup_node=10, delivery_node=20, weight_tonnes=3.0)
    driver.assign_order(order)
    driver.current_location = 10
    driver.step(current_hour=12)  # Arrive at pickup
    driver.step(current_hour=12)  # Loading → EN_ROUTE_DELIVERY
    assert driver.state == FreightState.EN_ROUTE_DELIVERY

    # Now simulate arrival at delivery during restriction hour
    driver.current_location = 20
    state = driver.step(current_hour=8)  # Restricted!
    # Should NOT transition to UNLOADING; stays in EN_ROUTE_DELIVERY
    assert state == FreightState.EN_ROUTE_DELIVERY


# ---------------------------------------------------------------------------
# Fare calculation
# ---------------------------------------------------------------------------

def test_freight_fare_baseline() -> None:
    """5t cargo, 10km, no fuel delta → baseline fare."""
    fare = FreightDriver.calculate_freight_fare(
        distance_km=10.0, weight_tonnes=5.0, fuel_price_delta_paise=0
    )
    # weight_factor = 1.0 for ≤5t; base = 18 * 10 * 1.0 = 180
    assert fare == pytest.approx(180.0)


def test_freight_fare_weight_scaling() -> None:
    """Heavier cargo pays more per km."""
    fare_light = FreightDriver.calculate_freight_fare(distance_km=10.0, weight_tonnes=5.0)
    fare_heavy = FreightDriver.calculate_freight_fare(distance_km=10.0, weight_tonnes=20.0)
    assert fare_heavy > fare_light


def test_freight_fare_fuel_sensitivity() -> None:
    """Freight pays 100% of fuel price delta as surcharge."""
    fare_no_delta = FreightDriver.calculate_freight_fare(
        distance_km=10.0, weight_tonnes=5.0, fuel_price_delta_paise=0
    )
    fare_with_delta = FreightDriver.calculate_freight_fare(
        distance_km=10.0, weight_tonnes=5.0, fuel_price_delta_paise=1000  # ₹10/km extra
    )
    # Expected surcharge: (1000 paise / 100) * 10 km = ₹100 extra
    assert fare_with_delta == pytest.approx(fare_no_delta + 100.0)


def test_freight_fare_zero_delta_unchanged() -> None:
    """Zero fuel delta does not change the fare."""
    fare_a = FreightDriver.calculate_freight_fare(distance_km=5.0, weight_tonnes=8.0)
    fare_b = FreightDriver.calculate_freight_fare(
        distance_km=5.0, weight_tonnes=8.0, fuel_price_delta_paise=0
    )
    assert fare_a == pytest.approx(fare_b)
