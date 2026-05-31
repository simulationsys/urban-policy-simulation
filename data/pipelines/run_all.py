#!/usr/bin/env python3
"""Master pipeline runner: execute all stages in sequence."""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
PIPELINE_DIR = PROJECT_ROOT / "data" / "pipelines"

STAGES = [
    ("01_download_osm_delhi.py", "Download OSM"),
    ("02_download_gtfs_delhi.py", "Download GTFS"),
    ("03_clean_road_network.py", "Clean road network"),
    ("04_parse_gtfs_to_network.py", "Parse GTFS"),
    ("05_generate_population_delhi.py", "Generate population"),
    ("06_validate_outputs.py", "Validate outputs"),
]


def run_stage(script_name: str, description: str) -> bool:
    """Run a single pipeline stage."""
    print(f"\n{'='*60}")
    print(f"STAGE: {description}")
    print(f"{'='*60}\n")

    script_path = PIPELINE_DIR / script_name
    if not script_path.exists():
        print(f"✗ Script not found: {script_path}")
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=PROJECT_ROOT,
            check=False
        )
        return result.returncode == 0
    except Exception as e:
        print(f"✗ Error running {script_name}: {e}")
        return False


def main():
    print("\n╔════════════════════════════════════════════════════════╗")
    print("║  DELHI DATA ENGINEERING PIPELINE                       ║")
    print("╚════════════════════════════════════════════════════════╝")

    results = {}
    for script, description in STAGES:
        success = run_stage(script, description)
        results[description] = success
        if not success:
            print(f"\n⚠ Stage failed: {description}")
            print("Continue? (y/n)")
            if input().lower() != 'y':
                break

    print(f"\n{'='*60}")
    print("PIPELINE SUMMARY")
    print(f"{'='*60}\n")

    for description, success in results.items():
        status = "✓" if success else "✗"
        print(f"{status} {description}")

    all_passed = all(results.values())
    if all_passed:
        print("\n✓ All stages completed successfully!")
    else:
        print("\n⚠ Some stages failed or were skipped.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
