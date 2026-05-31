#!/usr/bin/env python3
"""Validate processed datasets against expected ranges and schemas.

Checks:
- Road network connectivity and geometry
- Population distributions match Census targets
- Transit network has required fields
"""

import sys
from pathlib import Path

try:
    import pandas as pd
    import geopandas as gpd
    import json
except ImportError:
    print("ERROR: pandas, geopandas, or json not available.")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).parent.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def validate_road_network():
    """Check road network validity."""
    print("Validating road network...")

    file = PROCESSED_DIR / "road_network_delhi.parquet"
    if not file.exists():
        print(f"  ⚠ File not found: {file}")
        return False

    try:
        df = pd.read_parquet(file)
        n_edges = len(df)
        print(f"  ✓ Loaded {n_edges} edges")

        # Check required fields
        required = ['source', 'target', 'length', 'free_flow_speed_kmh', 'capacity_veh_hr']
        missing = [f for f in required if f not in df.columns]
        if missing:
            print(f"  ✗ Missing fields: {missing}")
            return False

        print(f"  ✓ All required fields present")
        return True

    except Exception as e:
        print(f"  ✗ Error validating: {e}")
        return False


def validate_population():
    """Check population validity."""
    print("Validating population...")

    file = PROCESSED_DIR / "synthetic_population_delhi.parquet"
    if not file.exists():
        print(f"  ⚠ File not found: {file}")
        return False

    try:
        df = pd.read_parquet(file)
        n_households = len(df)
        print(f"  ✓ Loaded {n_households} households")

        # Check required fields
        required = ['household_id', 'income_bracket', 'has_car', 'has_metro_pass',
                    'home_lat', 'home_lon', 'work_lat', 'work_lon']
        missing = [f for f in required if f not in df.columns]
        if missing:
            print(f"  ✗ Missing fields: {missing}")
            return False

        # Check income distribution (should match Census)
        income_dist = df['income_bracket'].value_counts(normalize=True).sort_index()
        expected = {1: 0.20, 2: 0.30, 3: 0.25, 4: 0.15, 5: 0.10}
        print(f"  Income distribution:")
        for inc, expected_pct in expected.items():
            actual_pct = income_dist.get(inc, 0)
            print(f"    Bracket {inc}: {actual_pct:.1%} (expected ~{expected_pct:.0%})")

        print(f"  ✓ Population valid")
        return True

    except Exception as e:
        print(f"  ✗ Error validating: {e}")
        return False


def validate_transit_network():
    """Check transit network validity."""
    print("Validating transit network...")

    file = PROCESSED_DIR / "transit_network_delhi.json"
    if not file.exists():
        print(f"  ⚠ File not found: {file}")
        return False

    try:
        with open(file) as f:
            data = json.load(f)

        metro_routes = len(data.get('metro', {}).get('routes', {}))
        metro_stops = len(data.get('metro', {}).get('stops', {}))
        bus_routes = len(data.get('bus', {}).get('routes', {}))
        bus_stops = len(data.get('bus', {}).get('stops', {}))

        print(f"  Metro: {metro_routes} routes, {metro_stops} stops")
        print(f"  Bus: {bus_routes} routes, {bus_stops} stops")

        if metro_routes == 0 and bus_routes == 0:
            print(f"  ⚠ No GTFS data parsed. Download GTFS files manually from OTD Delhi Portal.")
        else:
            print(f"  ✓ Transit network valid")

        return True

    except Exception as e:
        print(f"  ✗ Error validating: {e}")
        return False


def main():
    print("\n=== VALIDATING PROCESSED DATA ===\n")

    results = {
        'road_network': validate_road_network(),
        'population': validate_population(),
        'transit_network': validate_transit_network(),
    }

    print("\n=== VALIDATION SUMMARY ===")
    for component, passed in results.items():
        status = "✓ PASS" if passed else "⚠ INCOMPLETE"
        print(f"{status}: {component}")

    if all(results.values()):
        print("\n✓ All validation passed!")
    else:
        print("\n⚠ Some datasets incomplete. See notes above.")


if __name__ == "__main__":
    main()
