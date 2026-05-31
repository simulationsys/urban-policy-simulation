#!/usr/bin/env python3
"""Generate synthetic population for Delhi based on Census 2011 data.

Creates household-level population with demographic attributes.
Uses gravity model for workplace assignment.

Input: Census 2011 demographic data (stub)
Output: data/processed/synthetic_population_delhi.parquet
"""

import sys
from pathlib import Path

try:
    import numpy as np
    import pandas as pd
except ImportError:
    print("ERROR: numpy or pandas not installed.")
    print("Install with: pip install numpy pandas")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).parent.parent.parent
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "synthetic_population_delhi.parquet"

# Stub Census 2011 distributions for Delhi
INCOME_DISTRIBUTION = {1: 0.20, 2: 0.30, 3: 0.25, 4: 0.15, 5: 0.10}
CAR_OWNERSHIP_BY_INCOME = {1: 0.02, 2: 0.08, 3: 0.20, 4: 0.45, 5: 0.70}
BIKE_OWNERSHIP_BY_INCOME = {1: 0.10, 2: 0.30, 3: 0.50, 4: 0.55, 5: 0.45}
METRO_PASS_PROB = 0.25

# Rajiv Chowk center (4km radius - average of 3-5 km range)
RAJIV_CHOWK_LAT, RAJIV_CHOWK_LON = 28.6328, 77.2197
RADIUS_KM = 0.036  # ~4 km in degrees
DELHI_LAT_MIN, DELHI_LAT_MAX = RAJIV_CHOWK_LAT - RADIUS_KM, RAJIV_CHOWK_LAT + RADIUS_KM
DELHI_LON_MIN, DELHI_LON_MAX = RAJIV_CHOWK_LON - RADIUS_KM, RAJIV_CHOWK_LON + RADIUS_KM


def generate_population(n_households: int, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic household population."""
    rng = np.random.default_rng(seed)

    # Income distribution
    incomes = rng.choice(
        [1, 2, 3, 4, 5],
        size=n_households,
        p=[INCOME_DISTRIBUTION[i] for i in range(1, 6)]
    )

    # Household size
    household_sizes = rng.integers(1, 6, size=n_households)

    # Age of head (simplified)
    head_ages = rng.integers(25, 70, size=n_households)

    # Vehicle ownership
    has_car = np.array([
        bool(rng.random() < CAR_OWNERSHIP_BY_INCOME[inc])
        for inc in incomes
    ])
    has_bike = np.array([
        bool(rng.random() < BIKE_OWNERSHIP_BY_INCOME[inc])
        for inc in incomes
    ])
    has_metro_pass = rng.random(n_households) < METRO_PASS_PROB

    # Home locations (uniform within Delhi bounds)
    home_lats = rng.uniform(DELHI_LAT_MIN, DELHI_LAT_MAX, n_households)
    home_lons = rng.uniform(DELHI_LON_MIN, DELHI_LON_MAX, n_households)

    # Work locations (gravity model: closer to Rajiv Chowk, higher density)
    work_lats = rng.normal(RAJIV_CHOWK_LAT, 0.01, n_households)
    work_lons = rng.normal(RAJIV_CHOWK_LON, 0.01, n_households)

    df = pd.DataFrame({
        'household_id': np.arange(n_households),
        'income_bracket': incomes,
        'household_size': household_sizes,
        'head_age': head_ages,
        'has_car': has_car,
        'has_bike': has_bike,
        'has_metro_pass': has_metro_pass,
        'home_lat': home_lats,
        'home_lon': home_lons,
        'work_lat': work_lats,
        'work_lon': work_lons,
    })

    return df


def main():
    print("Generating synthetic population for Delhi...")

    try:
        # Generate ~1,429 households (~5,000 individuals at avg 3.5 members/household)
        n_households = 1429
        df = generate_population(n_households)

        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(OUTPUT_FILE)

        print(f"✓ Generated {n_households} households")
        print(f"  Total individuals: ~{int(df['household_size'].sum())}")
        print(f"  Saved to {OUTPUT_FILE}")

        # Summary stats
        print(f"\n  Income distribution:")
        for inc in range(1, 6):
            pct = (df['income_bracket'] == inc).sum() / len(df) * 100
            print(f"    Bracket {inc}: {pct:.1f}%")

        print(f"\n  Vehicle ownership:")
        print(f"    Has car: {df['has_car'].sum() / len(df) * 100:.1f}%")
        print(f"    Has bike: {df['has_bike'].sum() / len(df) * 100:.1f}%")
        print(f"    Metro pass: {df['has_metro_pass'].sum() / len(df) * 100:.1f}%")

    except Exception as e:
        print(f"✗ Error generating population: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
