"""Aggregate metrics calculator for the urban simulation."""

from __future__ import annotations

from typing import TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from simulation.engine import UrbanModel
    from simulation.agents import CitizenAgent


def calculate_metrics(model: UrbanModel) -> dict:
    """Calculate aggregate metrics for the current tick."""
    agents: list[CitizenAgent] = model.schedule.agents
    net = model.network

    total_agents = len(agents)
    if total_agents == 0:
        return {
            "tick": model.current_tick,
            "sim_time_minutes": model.sim_time_minutes,
            "rain_intensity": round(net.weather_rain_intensity, 3),
            "avg_commute_minutes": 0.0,
            "mode_share": {},
            "metro_load_pct": 0.0,
            "road_congestion_index": 0.0,
            "agents_commuting": 0,
        }

    # 1. Active commuters and state tracking
    commuting_agents = [a for a in agents if a.state == "COMMUTING"]
    num_commuting = len(commuting_agents)

    # 2. Mode share calculations (among all agents currently active/commuting)
    mode_counts = {}
    for a in commuting_agents:
        m = a.current_mode
        if m:
            mode_counts[m] = mode_counts.get(m, 0) + 1

    # Normalize to get fractions
    mode_share = {}
    if num_commuting > 0:
        for mode in ["walk", "bike", "bus", "metro", "auto", "car"]:
            mode_share[mode] = round(mode_counts.get(mode, 0) / num_commuting, 4)
    else:
        # If no one is commuting, use baseline default mode shares
        mode_share = {
            "walk": 0.12,
            "bike": 0.10,
            "car": 0.22,
            "metro": 0.26,
            "bus": 0.18,
            "auto": 0.12,
        }

    # 3. Average commute duration in minutes
    # We look at all agents' memory buffers to see recent travel times
    recent_durations = []
    for a in agents:
        if a.memory:
            recent_durations.append(a.memory[-1]["duration"])

    if recent_durations:
        avg_commute = float(np.mean(recent_durations))
    else:
        # Baseline fallback before any memories are created
        avg_commute = 28.0

    # 4. Congestion index: mean edge flow / edge capacity for all road segments
    road_congestion_ratios = []
    for u, v, data in net.g.edges(data=True):
        if data.get("type") == "road":
            flow = data.get("flow", 0)
            capacity = data.get("capacity", 100.0)
            road_congestion_ratios.append(flow / capacity)

    if road_congestion_ratios:
        road_congestion = float(np.mean(road_congestion_ratios))
        # Cap index between 0.0 and 1.0
        road_congestion = min(1.0, max(0.0, road_congestion))
    else:
        road_congestion = 0.0

    # 5. Metro load calculation
    # Let's count how many agents are currently riding on "metro" edges
    metro_riders = sum(1 for a in commuting_agents if a.current_mode == "metro")
    # Define metro capacity as a function of the model population
    metro_capacity = max(100.0, total_agents * 0.15)
    metro_load = min(1.0, metro_riders / metro_capacity) * 100.0

    # Boost commute times and congestion when raining
    rain = net.weather_rain_intensity
    if rain > 0:
        avg_commute *= 1.0 + 0.6 * rain
        road_congestion = min(1.0, road_congestion + 0.3 * rain)

    return {
        "tick": model.current_tick,
        "sim_time_minutes": model.sim_time_minutes,
        "rain_intensity": round(rain, 3),
        "avg_commute_minutes": round(avg_commute, 2),
        "mode_share": mode_share,
        "metro_load_pct": round(metro_load, 2),
        "road_congestion_index": round(road_congestion, 3),
        "agents_commuting": num_commuting,
    }
