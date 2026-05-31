#!/usr/bin/env python3
"""Download GTFS feeds for DMRC (Delhi Metro) and DTC (Delhi Buses).

Output: data/raw/gtfs_dmrc/ (DMRC static GTFS)
        data/raw/gtfs_dtc/  (DTC static GTFS)

NOTE: This script requires manual setup or API key from Open Transit Data (OTD) Delhi Portal.
For now, it generates mock GTFS files for demo purposes.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
import csv

DMRC_DIR = Path(__file__).parent.parent / "raw" / "gtfs_dmrc"
DTC_DIR = Path(__file__).parent.parent / "raw" / "gtfs_dtc"
DMRC_DIR.mkdir(parents=True, exist_ok=True)
DTC_DIR.mkdir(parents=True, exist_ok=True)

DMRC_LINES = {
    "purple": {"name": "Purple Line", "stations": 40, "capacity": 60000},
    "red": {"name": "Red Line", "stations": 36, "capacity": 55000},
    "blue": {"name": "Blue Line", "stations": 48, "capacity": 70000},
    "yellow": {"name": "Yellow Line", "stations": 34, "capacity": 50000},
    "green": {"name": "Green Line", "stations": 32, "capacity": 48000},
    "pink": {"name": "Pink Line", "stations": 28, "capacity": 45000},
}


def create_mock_dmrc_gtfs():
    """Create mock DMRC GTFS files."""
    print("[02] Creating mock DMRC GTFS files...")
    
    station_id = 0
    
    with open(DMRC_DIR / "stops.txt", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["stop_id", "stop_name", "stop_lat", "stop_lon", "line_id"])
        writer.writeheader()
        
        for line_code, line_info in DMRC_LINES.items():
            for i in range(line_info["stations"]):
                writer.writerow({
                    "stop_id": f"dmrc_{line_code}_stn_{i}",
                    "stop_name": f"{line_info['name']} Station {i+1}",
                    "stop_lat": 28.5355 + i * 0.01,
                    "stop_lon": 77.3910 + i * 0.01,
                    "line_id": line_code,
                })
                station_id += 1
    print(f"  → Created {station_id} mock stops in stops.txt")
    
    with open(DMRC_DIR / "routes.txt", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["route_id", "route_short_name", "route_long_name", "route_type"])
        writer.writeheader()
        for line_code, line_info in DMRC_LINES.items():
            writer.writerow({
                "route_id": f"dmrc_{line_code}",
                "route_short_name": line_code.upper(),
                "route_long_name": line_info["name"],
                "route_type": "1",  # Subway
            })
    print(f"  → Created {len(DMRC_LINES)} routes")
    
    with open(DMRC_DIR / "calendar.txt", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "service_id", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
            "start_date", "end_date"
        ])
        writer.writeheader()
        writer.writerow({
            "service_id": "weekday",
            "monday": 1, "tuesday": 1, "wednesday": 1, "thursday": 1, "friday": 1,
            "saturday": 0, "sunday": 0,
            "start_date": "20260101", "end_date": "20261231",
        })
        writer.writerow({
            "service_id": "weekend",
            "monday": 0, "tuesday": 0, "wednesday": 0, "thursday": 0, "friday": 0,
            "saturday": 1, "sunday": 1,
            "start_date": "20260101", "end_date": "20261231",
        })
    print(f"  → Created calendar")
    
    print("[02] ✓ Mock DMRC GTFS created")


def create_mock_dtc_gtfs():
    """Create mock DTC (Delhi buses) GTFS files."""
    print("[02] Creating mock DTC GTFS files...")
    
    dtc_routes = 300  # Approximate number of DTC routes
    
    with open(DTC_DIR / "routes.txt", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["route_id", "route_short_name", "route_long_name", "route_type"])
        writer.writeheader()
        for i in range(dtc_routes):
            writer.writerow({
                "route_id": f"dtc_{i:03d}",
                "route_short_name": f"{i:03d}",
                "route_long_name": f"DTC Route {i+1}",
                "route_type": "3",  # Bus
            })
    print(f"  → Created {dtc_routes} mock bus routes")
    
    with open(DTC_DIR / "stops.txt", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["stop_id", "stop_name", "stop_lat", "stop_lon"])
        writer.writeheader()
        for i in range(dtc_routes * 2):  # ~2 stops per route on average
            writer.writerow({
                "stop_id": f"dtc_stop_{i}",
                "stop_name": f"DTC Stop {i+1}",
                "stop_lat": 28.4 + (i % 100) * 0.01,
                "stop_lon": 77.1 + (i // 100) * 0.01,
            })
    print(f"  → Created {dtc_routes * 2} mock bus stops")
    
    with open(DTC_DIR / "calendar.txt", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "service_id", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
            "start_date", "end_date"
        ])
        writer.writeheader()
        writer.writerow({
            "service_id": "weekday",
            "monday": 1, "tuesday": 1, "wednesday": 1, "thursday": 1, "friday": 1,
            "saturday": 0, "sunday": 0,
            "start_date": "20260101", "end_date": "20261231",
        })
    print(f"  → Created calendar")
    
    print("[02] ✓ Mock DTC GTFS created")


def download_real_gtfs():
    """
    Placeholder for real GTFS download from OTD Delhi Portal.
    To use real data, implement:
    1. Register at https://otd.delhi.gov.in (or OTD Delhi Portal URL)
    2. Get API key from developer portal
    3. Use requests library to fetch GTFS feeds
    4. Extract ZIP and place in gtfs_dmrc/ and gtfs_dtc/
    """
    print("[02] NOTE: Using mock GTFS data for demo")
    print("[02] To use real GTFS:")
    print("  1. Register at OTD Delhi Portal")
    print("  2. Get API key from developer console")
    print("  3. Download DMRC + DTC GTFS feeds")
    print("  4. Extract to data/raw/gtfs_dmrc/ and data/raw/gtfs_dtc/")
    print()


if __name__ == "__main__":
    download_real_gtfs()
    create_mock_dmrc_gtfs()
    create_mock_dtc_gtfs()
    print("[02] ✓ GTFS download complete")
    sys.exit(0)
