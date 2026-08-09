"""Tests for ride-hail surge pricing model (RideHailSurge)."""

from __future__ import annotations

import numpy as np
import pytest

from sim.agents.alternatives import default_alternatives
from sim.agents.mode_choice import ModeChoiceModel
from sim.agents.modes import Mode
from sim.agents.ride_hail import RideHailSurge
from sim.scripts.demo_two_agents import make_priya, make_rohan


# ---------------------------------------------------------------------------
# RideHailSurge unit tests
# ---------------------------------------------------------------------------

def test_no_surge_baseline() -> None:
    """Off-peak, dry, balanced supply → multiplier is exactly 1.0."""
    surge = RideHailSurge()
    mult = surge.surge_multiplier(hour=14, rain_intensity=0.0, demand_ratio=1.0)
    assert mult == pytest.approx(1.0)


def test_surge_peak_hour_am() -> None:
    """AM peak (8–10) adds the peak_bonus."""
    surge = RideHailSurge()
    mult = surge.surge_multiplier(hour=9, rain_intensity=0.0, demand_ratio=1.0)
    assert mult == pytest.approx(1.0 + surge.peak_bonus)


def test_surge_peak_hour_pm() -> None:
    """PM peak (17–20) adds the peak_bonus."""
    surge = RideHailSurge()
    mult = surge.surge_multiplier(hour=18, rain_intensity=0.0, demand_ratio=1.0)
    assert mult == pytest.approx(1.0 + surge.peak_bonus)


def test_surge_off_peak_no_bonus() -> None:
    """Mid-day (13:00) is not peak — no bonus applied."""
    surge = RideHailSurge()
    mult = surge.surge_multiplier(hour=13, rain_intensity=0.0, demand_ratio=1.0)
    assert mult == pytest.approx(1.0)


def test_surge_rain() -> None:
    """Rain intensity increases surge multiplier proportionally."""
    surge = RideHailSurge()
    mult_dry = surge.surge_multiplier(hour=14, rain_intensity=0.0, demand_ratio=1.0)
    mult_wet = surge.surge_multiplier(hour=14, rain_intensity=0.5, demand_ratio=1.0)
    assert mult_wet > mult_dry
    assert mult_wet == pytest.approx(1.0 + 0.5 * surge.rain_surge_coeff)


def test_surge_demand_above_supply() -> None:
    """Demand ratio > 1.0 pushes multiplier above baseline."""
    surge = RideHailSurge()
    mult = surge.surge_multiplier(hour=14, rain_intensity=0.0, demand_ratio=2.0)
    # demand_ratio - 1.0 = 1.0 → adds demand_surge_coeff
    assert mult == pytest.approx(1.0 + surge.demand_surge_coeff)


def test_surge_cap_never_exceeded() -> None:
    """Surge multiplier is capped at max_surge_cap regardless of inputs."""
    surge = RideHailSurge()
    mult = surge.surge_multiplier(hour=9, rain_intensity=1.0, demand_ratio=5.0)
    assert mult == pytest.approx(surge.max_surge_cap)


def test_fare_minimum_enforced() -> None:
    """Very short trips still charge at least the minimum fare."""
    surge = RideHailSurge(base_min_fare=30.0, base_fare_per_km=12.0)
    fare = surge.fare(distance_km=0.5, multiplier=1.0)
    assert fare == pytest.approx(30.0)


def test_fare_scales_with_surge() -> None:
    """Fare at 2x surge is double compared to no-surge for same distance."""
    surge = RideHailSurge(base_min_fare=0.0)
    fare_1x = surge.fare(distance_km=10.0, multiplier=1.0)
    fare_2x = surge.fare(distance_km=10.0, multiplier=2.0)
    assert fare_2x == pytest.approx(2.0 * fare_1x)


# ---------------------------------------------------------------------------
# Integration with ModeChoiceModel
# ---------------------------------------------------------------------------

def test_low_income_avoids_surge_ride_hail() -> None:
    """Bracket-1 Priya should not pick ride-hail when surge is 3x (too expensive)."""
    model = ModeChoiceModel(rng=np.random.default_rng(42))
    priya = make_priya()
    # 3× surge — ride-hail is ₹36/km, far too expensive for bracket-1
    alts = default_alternatives(priya, distance_km=10.0, surge_multiplier=3.0)
    choice = model.choose(priya, alts, stochastic=False)
    assert choice != Mode.RIDE_HAIL


def test_high_income_ride_hail_in_rain() -> None:
    """Bracket-5 Rohan should prefer ride-hail over auto in heavy rain (comfortable + sheltered)."""
    model = ModeChoiceModel(rng=np.random.default_rng(0))
    rohan = make_rohan()
    # No surge, but heavy rain — ride-hail has 0.1 rain exposure vs auto 0.5
    alts = default_alternatives(rohan, distance_km=10.0, rain_intensity=1.0, surge_multiplier=1.0)
    choice = model.choose(rohan, alts, stochastic=False)
    # Rohan (high income, comfort-driven) should prefer car or ride-hail over metro/bus in rain
    assert choice in (Mode.CAR, Mode.RIDE_HAIL)


def test_ride_hail_always_available() -> None:
    """All agents (no car, no bike) still have RIDE_HAIL in available modes."""
    priya = make_priya()
    priya.has_bike = False
    priya.has_car = False
    assert Mode.RIDE_HAIL in priya.available_modes()
