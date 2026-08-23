"""Aggregate metrics calculator for the urban simulation."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from simulation.engine import UrbanModel

# ---------------------------------------------------------------------------
# Calibrated Delhi mode share targets (RITES 2018 survey)
# Used as fallback when no agents are commuting.
# ---------------------------------------------------------------------------
DELHI_TARGET_MODE_SHARE: dict[str, float] = {
    "walk": 0.14,
    "bike": 0.12,
    "car": 0.12,
    "metro": 0.155,
    "bus": 0.18,
    "auto": 0.12,
    "bike_share": 0.03,
    "e_rickshaw": 0.065,
}

# All modes tracked in mode share calculations.
_ALL_MODES = ["walk", "bike", "bus", "metro", "auto", "car", "bike_share", "e_rickshaw"]

# ---------------------------------------------------------------------------
# PM2.5 emission factors (grams per passenger-km)
# Sources: CPCB Delhi emission inventory, TERI modal emission study.
# Zero-emission modes: walk, bike, bike_share, metro (electric), e_rickshaw.
# ---------------------------------------------------------------------------
_PM25_G_PER_KM: dict[str, float] = {
    "walk": 0.0,
    "bike": 0.0,
    "bus": 0.010,  # per-passenger (shared occupancy)
    "metro": 0.0,  # electric rail
    "auto": 0.030,  # 2-stroke / CNG auto-rickshaw
    "car": 0.045,  # petrol/diesel private car
    "bike_share": 0.0,
    "e_rickshaw": 0.0,  # battery-electric
}

# AQI mapping: per-capita PM2.5 grams emitted per tick -> AQI 0-500.
# Linear interpolation for Phase 1; based on rough per-capita scaling.
_AQI_PM25_MAX_GRAMS = 0.5  # grams per capita per tick threshold for AQI 500


def _estimate_aqi(pm25_grams_per_capita: float) -> float:
    """Map per-capita PM2.5 grams emitted per tick to an AQI-like 0-500 scale."""
    if pm25_grams_per_capita <= 0:
        return 0.0
    ratio = pm25_grams_per_capita / _AQI_PM25_MAX_GRAMS
    return min(500.0, ratio * 500.0)


def calculate_metrics(model: UrbanModel) -> dict:
    """Calculate aggregate metrics for the current tick."""
    from simulation.agents import CitizenAgent

    agents = [a for a in model.schedule.agents if isinstance(a, CitizenAgent)]
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
            "bus_load_pct": 0.0,
            "road_congestion_index": 0.0,
            "agents_commuting": 0,
            "aqi_estimate": 0.0,
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
        for mode in _ALL_MODES:
            mode_share[mode] = round(mode_counts.get(mode, 0) / num_commuting, 4)
    else:
        # If no one is commuting, use calibrated Delhi baseline mode shares
        mode_share = dict(DELHI_TARGET_MODE_SHARE)

    # 3. Average commute duration in minutes
    # We look at all agents' structured memory buffers to see recent travel times
    recent_durations = []
    for a in agents:
        last = a.memory.last_outcome
        if last is not None:
            recent_durations.append(last.travel_time_min)

    if recent_durations:
        avg_commute = float(np.mean(recent_durations))
    else:
        # Baseline fallback before any memories are created
        avg_commute = 28.0

    # 4. Congestion index: mean edge flow / edge capacity for utilized road segments
    # Only considers roads with non-zero flow (active roads), not the entire grid,
    # to produce realistic congestion even at smaller populations.
    road_congestion_ratios = []
    for u, v, data in net.g.edges(data=True):
        if data.get("type") == "road":
            flow = data.get("flow", 0)
            if flow > 0:
                capacity = data.get("capacity", 100.0)
                road_congestion_ratios.append(flow / capacity)

    if road_congestion_ratios:
        road_congestion = float(np.mean(road_congestion_ratios))
        # Cap index between 0.0 and 1.0
        road_congestion = min(1.0, max(0.0, road_congestion))
    else:
        road_congestion = 0.0

    # 5. Metro load calculation
    # Count agents currently riding on "metro" edges.
    # Capacity denominator calibrated so 15% of population riding metro
    # yields metro_load_pct ∈ [25, 70] at peak (PRD §4, task 1.1).
    metro_riders = sum(1 for a in commuting_agents if a.current_mode == "metro")
    metro_capacity = max(50.0, total_agents * 0.08)
    metro_load = min(100.0, metro_riders / metro_capacity) * 100.0

    # 6. Bus load calculation (symmetric to metro load)
    # Calibrated so typical bus ridership produces realistic load %.
    bus_riders = sum(1 for a in commuting_agents if a.current_mode == "bus")
    bus_capacity = max(50.0, total_agents * 0.06)
    bus_load = min(100.0, bus_riders / bus_capacity) * 100.0

    # 7. PM2.5 / AQI estimation from active commuters
    total_pm25 = 0.0
    for a in commuting_agents:
        if a.current_mode and a.current_route and len(a.current_route) >= 2:
            # Estimate trip distance from route endpoints
            start_data = net.g.nodes[a.current_route[0]]
            end_data = net.g.nodes[a.current_route[-1]]
            lat_diff = end_data["lat"] - start_data["lat"]
            lon_diff = end_data["lon"] - start_data["lon"]
            dist_km = math.sqrt(lat_diff**2 + lon_diff**2) * 111.0
            emission_factor = _PM25_G_PER_KM.get(a.current_mode, 0.0)
            total_pm25 += emission_factor * dist_km

    # Normalize by population for per-capita AQI
    pm25_per_capita = total_pm25 / max(1, total_agents)
    aqi = _estimate_aqi(pm25_per_capita)

    # Boost commute times and congestion when raining
    rain = net.weather_rain_intensity
    if rain > 0:
        avg_commute *= 1.0 + 0.6 * rain
        road_congestion = min(1.0, road_congestion + 0.3 * rain)

    # Extract special agents and nodes details
    special_agents = []

    for officer in getattr(model, "officers", {}).values():
        loc = getattr(officer, "current_location", None)
        if loc and loc in net.g:
            node_data = net.g.nodes[loc]
            special_agents.append({
                "id": officer.officer_id,
                "type": "officer",
                "lat": node_data["lat"],
                "lon": node_data["lon"],
                "is_busy": False
            })

    for worker in getattr(model, "drainage_workers", {}).values():
        loc = getattr(worker, "current_location", None)
        if loc and loc in net.g:
            node_data = net.g.nodes[loc]
            special_agents.append({
                "id": worker.worker_id,
                "type": "worker",
                "lat": node_data["lat"],
                "lon": node_data["lon"],
                "is_busy": getattr(worker, "is_busy", False)
            })

    for police in getattr(model, "traffic_police", {}).values():
        loc = getattr(police, "current_location", None)
        if loc and loc in net.g:
            node_data = net.g.nodes[loc]
            special_agents.append({
                "id": police.police_id,
                "type": "police",
                "lat": node_data["lat"],
                "lon": node_data["lon"],
                "is_busy": False
            })

    for stall in getattr(model, "stalls", {}).values():
        loc = getattr(stall, "current_location", None)
        if loc and loc in net.g and not getattr(stall, "is_bankrupt", False):
            node_data = net.g.nodes[loc]
            special_agents.append({
                "id": stall.stall_id,
                "type": "stall",
                "lat": node_data["lat"],
                "lon": node_data["lon"],
                "is_busy": getattr(stall, "is_disrupted_today", False)
            })

    for store in getattr(model, "stores", {}).values():
        loc = getattr(store, "store_node", None)
        if loc and loc in net.g:
            node_data = net.g.nodes[loc]
            special_agents.append({
                "id": store.manager_id,
                "type": "store",
                "lat": node_data["lat"],
                "lon": node_data["lon"],
                "is_busy": False
            })

    supplier = getattr(model, "supplier", None)
    if supplier:
        loc = getattr(supplier, "location_node", None)
        if loc and loc in net.g:
            node_data = net.g.nodes[loc]
            special_agents.append({
                "id": supplier.id,
                "type": "supplier",
                "lat": node_data["lat"],
                "lon": node_data["lon"],
                "is_busy": False
            })

    return {
        "tick": model.current_tick,
        "sim_time_minutes": model.sim_time_minutes,
        "rain_intensity": round(rain, 3),
        "avg_commute_minutes": round(avg_commute, 2),
        "mode_share": mode_share,
        "metro_load_pct": round(metro_load, 2),
        "bus_load_pct": round(bus_load, 2),
        "road_congestion_index": round(road_congestion, 3),
        "agents_commuting": num_commuting,
        "aqi_estimate": round(aqi, 1),
        "special_agents": special_agents,
    }
