"""Calibration script for mode choice utility weights against Delhi 2018 State Transport Survey targets.

Uses randomized hill climbing search to find the optimal utility weights and comfort profiles.
"""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import numpy as np

import sim.agents.alternatives
from sim.agents.alternatives import default_alternatives, _PROFILE
import sim.agents.utility_weights
from sim.agents.utility_weights import UtilityWeights
from sim.agents.modes import Mode, Occupation
from sim.agents.population import build_population
from sim.agents.mode_choice import ModeChoiceModel

TARGETS = {
    "bike": 0.285,
    "walk_auto": 0.260,
    "bus": 0.180,
    "metro": 0.155,
    "car": 0.120,
}

# Define the set of parameters we want to tune
# We'll represent parameters as a dictionary of key-value pairs
# Profile comforts:
#   comfort_walk, comfort_bike, comfort_bus, comfort_metro, comfort_auto, comfort_car
# Base weights:
#   For each occupation, we can tune beta_time, beta_cost, beta_comfort

def apply_params(params: dict[str, float]) -> None:
    # 1. Update _PROFILE comforts in alternatives.py to original baseline values
    sim.agents.alternatives._PROFILE[Mode.WALK] = (12.0, 0.0, 0.30)
    sim.agents.alternatives._PROFILE[Mode.BIKE] = (4.0, 0.5, 0.40)
    sim.agents.alternatives._PROFILE[Mode.BUS] = (5.0, 1.5, 0.45)
    sim.agents.alternatives._PROFILE[Mode.METRO] = (3.0, 3.0, 0.65)
    sim.agents.alternatives._PROFILE[Mode.AUTO] = (3.5, 12.0, 0.55)
    sim.agents.alternatives._PROFILE[Mode.CAR] = (3.0, 8.0, 0.75)

    # 2. Overwrite UtilityWeights.for_occupation to return custom weights
    def mock_for_occupation(occupation: Occupation) -> UtilityWeights:
        if occupation == Occupation.OFFICE_EXECUTIVE:
            return UtilityWeights(
                beta_time=params["exec_beta_time"],
                beta_cost=params["exec_beta_cost"],
                beta_comfort=params["exec_beta_comfort"],
                beta_weather=-0.4,
                beta_habit=0.4,
            )
        elif occupation == Occupation.STUDENT:
            return UtilityWeights(
                beta_time=params["stud_beta_time"],
                beta_cost=params["stud_beta_cost"],
                beta_comfort=params["stud_beta_comfort"],
                beta_weather=-1.5,
                beta_habit=0.3,
            )
        elif occupation == Occupation.BLUE_COLLAR_WORKER:
            return UtilityWeights(
                beta_time=params["blue_beta_time"],
                beta_cost=params["blue_beta_cost"],
                beta_comfort=params["blue_beta_comfort"],
                beta_weather=-1.2,
                beta_habit=0.5,
            )
        elif occupation == Occupation.GIG_WORKER:
            return UtilityWeights(
                beta_time=params["gig_beta_time"],
                beta_cost=params["gig_beta_cost"],
                beta_comfort=params["gig_beta_comfort"],
                beta_weather=-1.0,
                beta_habit=0.2,
            )
        elif occupation == Occupation.RETIRED_CITIZEN:
            return UtilityWeights(
                beta_time=params["ret_beta_time"],
                beta_cost=params["ret_beta_cost"],
                beta_comfort=params["ret_beta_comfort"],
                beta_weather=-2.5,
                beta_habit=0.6,
            )
        return UtilityWeights(
            beta_time=params["default_beta_time"],
            beta_cost=params["default_beta_cost"],
            beta_comfort=params["default_beta_comfort"],
            beta_weather=-1.5,
            beta_habit=0.4,
        )

    sim.agents.utility_weights.UtilityWeights.for_occupation = staticmethod(mock_for_occupation)

def run_simulation(n: int = 5000, seed: int = 42, rain: float = 0.0) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    agents = build_population(n, rng=rng)
    model = ModeChoiceModel(rng=rng)

    counts: Counter[Mode] = Counter()
    for a in agents:
        dist = 2.0 + (a.id % 13)
        alts = default_alternatives(a, distance_km=dist, rain_intensity=rain)
        counts[model.choose(a, alts)] += 1

    return {m.value: counts.get(m, 0) / n for m in Mode}

def evaluate_shares(shares: dict[str, float]) -> tuple[float, dict[str, float]]:
    sim_walk_auto = shares.get("walk", 0.0) + shares.get("auto", 0.0)
    sim_bike = shares.get("bike", 0.0)
    sim_bus = shares.get("bus", 0.0)
    sim_metro = shares.get("metro", 0.0)
    sim_car = shares.get("car", 0.0)

    errors = {
        "bike": sim_bike - TARGETS["bike"],
        "walk_auto": sim_walk_auto - TARGETS["walk_auto"],
        "bus": sim_bus - TARGETS["bus"],
        "metro": sim_metro - TARGETS["metro"],
        "car": sim_car - TARGETS["car"],
    }

    rmse = np.sqrt(np.mean([err**2 for err in errors.values()]))
    return rmse, errors

def get_initial_params() -> dict[str, float]:
    return {
        "default_beta_time": -0.08,
        "default_beta_cost": -0.02,
        "default_beta_comfort": 0.5,

        "exec_beta_time": -0.15,
        "exec_beta_cost": -0.002,
        "exec_beta_comfort": 1.8,

        "stud_beta_time": -0.04,
        "stud_beta_cost": -0.08,
        "stud_beta_comfort": 0.1,

        "blue_beta_time": -0.10,
        "blue_beta_cost": -0.05,
        "blue_beta_comfort": 0.2,

        "gig_beta_time": -0.18,
        "gig_beta_cost": -0.06,
        "gig_beta_comfort": 0.1,

        "ret_beta_time": -0.03,
        "ret_beta_cost": -0.03,
        "ret_beta_comfort": 1.2,
    }

def print_params(params: dict[str, float]) -> None:
    print("\nOptimal Parameters Found:")
    print("--- Alternatives Profiles Comfort (Fixed to baseline) ---")
    print("  comfort_walk   : 0.30")
    print("  comfort_bike   : 0.40")
    print("  comfort_bus    : 0.45")
    print("  comfort_metro  : 0.65")
    print("  comfort_auto   : 0.55")
    print("  comfort_car    : 0.75")
    print("--- Default Weights ---")
    for k in ["default_beta_time", "default_beta_cost", "default_beta_comfort"]:
        print(f"  {k:20s}: {params[k]:.4f}")
    print("--- OFFICE_EXECUTIVE Weights ---")
    for k in ["exec_beta_time", "exec_beta_cost", "exec_beta_comfort"]:
        print(f"  {k:20s}: {params[k]:.4f}")
    print("--- STUDENT Weights ---")
    for k in ["stud_beta_time", "stud_beta_cost", "stud_beta_comfort"]:
        print(f"  {k:20s}: {params[k]:.4f}")
    print("--- BLUE_COLLAR_WORKER Weights ---")
    for k in ["blue_beta_time", "blue_beta_cost", "blue_beta_comfort"]:
        print(f"  {k:20s}: {params[k]:.4f}")
    print("--- GIG_WORKER Weights ---")
    for k in ["gig_beta_time", "gig_beta_cost", "gig_beta_comfort"]:
        print(f"  {k:20s}: {params[k]:.4f}")
    print("--- RETIRED_CITIZEN Weights ---")
    for k in ["ret_beta_time", "ret_beta_cost", "ret_beta_comfort"]:
        print(f"  {k:20s}: {params[k]:.4f}")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--search", action="store_true", help="Run hill-climbing search")
    parser.add_argument("--iters", type=int, default=1000, help="Number of search iterations")
    args = parser.parse_args()

    initial_params = get_initial_params()
    apply_params(initial_params)
    
    rng = np.random.default_rng(42)
    agents = build_population(5000, rng=rng)
    total = len(agents)
    has_bike_count = sum(1 for a in agents if a.has_bike)
    has_car_count = sum(1 for a in agents if a.has_car)
    
    print(f"Population size: {total}")
    print(f"Has bike: {has_bike_count} ({has_bike_count/total:.1%})")
    print(f"Has car: {has_car_count} ({has_car_count/total:.1%})")

    shares = run_simulation()
    rmse, errors = evaluate_shares(shares)
    
    print("\nInitial Mode Shares:")
    for mode, val in shares.items():
        print(f"  {mode:6s}: {val:.1%}")
    print(f"Combined walk+auto: {shares.get('walk', 0.0)+shares.get('auto', 0.0):.1%}")
    print(f"Initial RMSE: {rmse:.4f}")

    if not args.search:
        return

    best_params = copy.deepcopy(initial_params)
    best_rmse = rmse
    best_shares = shares

    print(f"\nStarting optimization search for {args.iters} iterations...")
    
    # We will adjust params step by step
    rng = np.random.default_rng(12345)
    
    # Helper to enforce bounds on parameters
    def clamp_param(name: str, val: float) -> float:
        if name == "comfort_walk":
            return max(0.20, min(0.40, val))
        if name == "comfort_bike":
            return max(0.30, min(0.50, val))
        if name == "comfort_bus":
            return max(0.35, min(0.55, val))
        if name == "comfort_metro":
            return max(0.55, min(0.75, val))
        if name == "comfort_auto":
            return max(0.45, min(0.65, val))
        if name == "comfort_car":
            return max(0.70, min(0.90, val))
        if "beta_time" in name:
            return min(-0.005, val) # must be negative
        if "beta_cost" in name:
            return min(-0.0005, val) # must be negative
        if "beta_comfort" in name:
            return max(0.0, val) # comfort weight usually non-negative
        return val

    # Hill climbing: perturb one parameter at a time or perturb all slightly
    step_size = 0.1
    for i in range(args.iters):
        # Decay step size over time
        current_step = step_size * (1.0 - i / args.iters) ** 0.5
        
        # Perturb parameters
        candidate = copy.deepcopy(best_params)
        
        # We can perturb a random subset of parameters
        n_perturbs = rng.integers(1, 4)
        keys_to_perturb = rng.choice(list(candidate.keys()), size=n_perturbs, replace=False)
        
        for k in keys_to_perturb:
            perturbation = rng.normal(0, current_step * 0.2)
            # Time and cost betas are small negative floats, so perturb proportionally or adjust scale
            if "beta_time" in k or "beta_cost" in k:
                # Proportional scale perturbation
                candidate[k] = clamp_param(k, candidate[k] * (1.0 + perturbation))
            else:
                candidate[k] = clamp_param(k, candidate[k] + perturbation)

        # Evaluate candidate
        apply_params(candidate)
        cand_shares = run_simulation()
        cand_rmse, _ = evaluate_shares(cand_shares)

        if cand_rmse < best_rmse:
            best_rmse = cand_rmse
            best_params = candidate
            best_shares = cand_shares
            print(f"Iter {i:4d}: Improved RMSE to {best_rmse:.4f}")
            if best_rmse < 0.005:  # Very close match
                print("Extremely close match found!")
                break

    print("\nOptimization Finished!")
    print(f"Best RMSE: {best_rmse:.4f}")
    print("Calibrated Mode Shares:")
    for mode, val in best_shares.items():
        print(f"  {mode:6s}: {val:.1%}")
    print(f"Combined walk+auto: {best_shares.get('walk', 0.0)+best_shares.get('auto', 0.0):.1%}")
    
    print_params(best_params)

if __name__ == "__main__":
    main()
