"""Build every processed input the simulation needs, in dependency order.

Without these files the engine falls back to a 10x10 synthetic lattice and citizens travel
in straight lines between grid points instead of along Delhi's streets. The outputs are
gitignored (see data/.gitignore), so this has to be run once per machine — and as part of
any deployment that wants the real road network:

    python data/pipelines/run_all.py

Outputs, all under data/processed_data/:
    network.graphml               OSM drive network, 4 km around Rajiv Chowk
    nodes.parquet, edges.parquet  tabular view of the same graph
    delhi_*.csv                   census-derived demographic distributions
    synthetic_population.parquet  5,000 agents with real home/work nodes
    weather_delhi.csv             monsoon weather archive

Steps are skipped when their outputs already exist; pass --force to rebuild.
"""

from __future__ import annotations

import argparse
import runpy
import sys
import time
from pathlib import Path

PIPELINES_DIR = Path(__file__).resolve().parent
OUT_DIR = PIPELINES_DIR.parent / "processed_data"

# (script, outputs it produces, why it matters, rebuild-if-these-steps-ran)
#
# The population stores OSM node ids, so it is only valid for the network it was built
# against. OSM changes daily and the connected-component trim moves with it, so rebuilding
# the network *must* rebuild the population — otherwise agents reference nodes that no
# longer exist and the engine has to guess where they live.
STEPS: list[tuple[str, list[str], str, tuple[str, ...]]] = [
    ("1_download_osm_network.py", ["network.graphml"], "real street network", ()),
    (
        "2_fetch_census_demographics.py",
        ["delhi_age_distribution.csv", "delhi_household_size.csv", "delhi_income_proxy.csv"],
        "census distributions",
        (),
    ),
    (
        "3_generate_population.py",
        ["synthetic_population.parquet"],
        "population with real nodes",
        ("1_download_osm_network.py", "2_fetch_census_demographics.py"),
    ),
    ("3_fetch_monsoon_weather.py", ["weather_delhi.csv"], "monsoon weather", ()),
]


def _outputs_present(outputs: list[str]) -> bool:
    return all((OUT_DIR / name).exists() for name in outputs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="rebuild even if outputs exist")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # osmnx caches downloads relative to the working directory, which would drop a multi-MB
    # `cache/` wherever this happens to be run from. Pin it next to the other data.
    try:
        import osmnx as ox

        ox.settings.cache_folder = str(PIPELINES_DIR.parent / "cache")
    except ImportError:
        pass  # step 1 will report the missing dependency itself

    failures: list[str] = []
    rebuilt: set[str] = set()

    for script, outputs, purpose, depends_on in STEPS:
        stale = any(dep in rebuilt for dep in depends_on)
        if not args.force and not stale and _outputs_present(outputs):
            print(f"[skip] {script} - {purpose} already built")
            continue
        if stale:
            print(f"[dep ] {script} - rebuilding, its inputs changed")

        print(f"[run ] {script} - {purpose}")
        rebuilt.add(script)
        started = time.time()
        try:
            # Each pipeline resolves its own paths relative to its file, so the working
            # directory does not matter; run in-process to keep one interpreter/env.
            runpy.run_path(str(PIPELINES_DIR / script), run_name="__main__")
        except SystemExit as exc:  # a pipeline calling sys.exit()
            if exc.code not in (0, None):
                failures.append(f"{script} (exit {exc.code})")
                print(f"[FAIL] {script}: exit code {exc.code}")
                continue
        except Exception as exc:
            failures.append(f"{script} ({exc.__class__.__name__}: {exc})")
            print(f"[FAIL] {script}: {exc.__class__.__name__}: {exc}")
            continue
        print(f"[ ok ] {script} in {time.time() - started:.1f}s")

    print("\nProcessed data in", OUT_DIR)
    for path in sorted(OUT_DIR.glob("*")):
        if path.is_file() and path.name != ".gitkeep":
            print(f"  {path.name:<32} {path.stat().st_size / 1024:>10.1f} KB")

    if failures:
        print("\nFAILED steps:")
        for f in failures:
            print("  -", f)
        print("\nThe engine will fall back to its synthetic grid for anything missing.")
        return 1

    print("\nAll inputs ready. Start the backend and it will pick these up automatically.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
