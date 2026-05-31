#!/usr/bin/env python3
"""Parse GTFS feeds (DMRC + DTC) into a unified transit network definition.

Input: data/raw/gtfs_dmrc/ and data/raw/gtfs_dtc/
Output: data/processed/transit_network_delhi.json
"""

import sys
import json
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas not installed.")
    print("Install with: pip install pandas")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).parent.parent.parent
GTFS_DMRC_DIR = PROJECT_ROOT / "data" / "raw" / "gtfs_dmrc"
GTFS_DTC_DIR = PROJECT_ROOT / "data" / "raw" / "gtfs_dtc"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "transit_network_delhi.json"


def load_gtfs_routes(gtfs_dir: Path, transit_type: str) -> dict:
    """Load routes, stops, and schedules from a GTFS directory."""
    data = {
        "type": transit_type,
        "routes": {},
        "stops": {}
    }

    try:
        # Load stops
        stops_file = gtfs_dir / "stops.txt"
        if stops_file.exists():
            stops_df = pd.read_csv(stops_file)
            for _, row in stops_df.iterrows():
                data["stops"][row['stop_id']] = {
                    "name": row.get('stop_name', ''),
                    "lat": row.get('stop_lat', 0),
                    "lon": row.get('stop_lon', 0),
                }

        # Load routes
        routes_file = gtfs_dir / "routes.txt"
        if routes_file.exists():
            routes_df = pd.read_csv(routes_file)
            for _, row in routes_df.iterrows():
                data["routes"][row['route_id']] = {
                    "name": row.get('route_long_name', row.get('route_short_name', '')),
                    "type": row.get('route_type', ''),
                }

    except Exception as e:
        print(f"  Warning: Error parsing {transit_type}: {e}")

    return data


def main():
    print("Parsing GTFS to transit network...")

    transit_network = {
        "metro": {"routes": {}, "stops": {}},
        "bus": {"routes": {}, "stops": {}}
    }

    # Parse DMRC (Metro)
    if GTFS_DMRC_DIR.exists() and list(GTFS_DMRC_DIR.glob("*.txt")):
        print("  Parsing DMRC (Metro)...")
        metro_data = load_gtfs_routes(GTFS_DMRC_DIR, "metro")
        transit_network["metro"] = metro_data
        print(f"    Routes: {len(metro_data['routes'])}, Stops: {len(metro_data['stops'])}")
    else:
        print(f"  ✗ DMRC GTFS not found in {GTFS_DMRC_DIR}")
        print("    Download from OTD Delhi Portal and extract manually.")

    # Parse DTC (Bus)
    if GTFS_DTC_DIR.exists() and list(GTFS_DTC_DIR.glob("*.txt")):
        print("  Parsing DTC (Bus)...")
        bus_data = load_gtfs_routes(GTFS_DTC_DIR, "bus")
        transit_network["bus"] = bus_data
        print(f"    Routes: {len(bus_data['routes'])}, Stops: {len(bus_data['stops'])}")
    else:
        print(f"  ✗ DTC GTFS not found in {GTFS_DTC_DIR}")
        print("    Download from OTD Delhi Portal and extract manually.")

    # Write output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(transit_network, f, indent=2)

    print(f"✓ Transit network saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
