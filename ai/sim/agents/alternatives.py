"""Synthetic mode alternatives for testing agent decisions in isolation.

These are stand-ins until SUB-03 (Transportation & Routing) provides real
travel-time and cost estimates per OD pair. The values are stylised but
roughly Indian-city-plausible per 10km commute.

Replace `default_alternatives()` with calls into SUB-03's routing service
when its API lands; the rest of SUB-02 can stay unchanged.
"""

from __future__ import annotations

from sim.agents.agent import Agent
from sim.agents.mode_choice import ModeAlternative
from sim.agents.modes import Mode

# Per-km rough estimates: (minutes/km, ₹/km, comfort 0..1)
_PROFILE: dict[Mode, tuple[float, float, float]] = {
    Mode.WALK:  (12.0, 0.0,  0.30),
    Mode.BIKE:  (4.0,  0.5,  0.40),
    Mode.BUS:   (5.0,  1.5,  0.45),
    Mode.METRO: (3.0,  3.0,  0.65),
    Mode.AUTO:  (3.5,  12.0, 0.55),
    Mode.CAR:   (3.0,  8.0,  0.75),
}

# How exposed each mode is to rain (0 = sheltered, 1 = fully exposed).
_RAIN_EXPOSURE: dict[Mode, float] = {
    Mode.WALK: 1.0,
    Mode.BIKE: 1.0,
    Mode.AUTO: 0.5,
    Mode.BUS: 0.2,
    Mode.METRO: 0.0,
    Mode.CAR: 0.0,
}


def default_alternatives(
    agent: Agent,
    *,
    distance_km: float,
    rain_intensity: float = 0.0,  # 0..1
) -> list[ModeAlternative]:
    """Build a list of ModeAlternatives the agent can actually use, given a trip distance."""
    alts: list[ModeAlternative] = []
    for mode in agent.available_modes():
        mins_per_km, rs_per_km, comfort = _PROFILE[mode]
        # Walk is only realistic for short trips.
        if mode == Mode.WALK and distance_km > 3.0:
            continue
        alts.append(
            ModeAlternative(
                mode=mode,
                travel_time_min=mins_per_km * distance_km,
                monetary_cost=rs_per_km * distance_km,
                comfort_score=comfort,
                weather_penalty=_RAIN_EXPOSURE[mode] * rain_intensity,
            )
        )
    return alts
