"""
Pipeline 1: Download OSM Drivable Street Network — Rajiv Chowk, New Delhi
=========================================================================

Downloads the drivable street network from OpenStreetMap centered on the
Rajiv Chowk metro station (28.6328° N, 77.2197° E) with a 2 km radius.

The string query "Rajiv Chowk, New Delhi, India" can be ambiguous (it may
refer to the intersection, the metro station, or the broader area), so we
use explicit coordinates with a fixed radius to guarantee reproducibility.

Outputs (written to ../processed_data/):
    - network.graphml   — full graph for NetworkX analysis
    - edges.parquet     — GeoDataFrame edge list for tabular / GIS workflows
"""

import os
import sys
from pathlib import Path

# Fix Windows console encoding (cp1252 cannot handle Unicode from OSM data)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import osmnx as ox
import geopandas as gpd

# ── Configuration ──────────────────────────────────────────────────────────
# Rajiv Chowk Metro Station coordinates (WGS-84)
CENTER_LAT = 28.6328
CENTER_LNG = 77.2197
RADIUS_M = 2000  # 2 km radius

NETWORK_TYPE = "drive"  # drivable roads only

# Output paths (relative to this script's location)
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR.parent / "processed_data"

GRAPHML_PATH = OUTPUT_DIR / "network.graphml"
PARQUET_PATH = OUTPUT_DIR / "edges.parquet"


def download_network(center_point: tuple, dist: int, network_type: str):
    """Download the street network from OSM within a circular buffer."""
    print(f"[1/4] Downloading {network_type} network "
          f"({dist}m around {center_point}) from OSM...")
    G = ox.graph_from_point(
        center_point,
        dist=dist,
        network_type=network_type,
        simplify=True,
    )
    print(f"       Raw graph: {G.number_of_nodes()} nodes, "
          f"{G.number_of_edges()} edges")
    return G


def clean_graph(G):
    """Clean the graph: remove isolated nodes, keep largest strongly-connected component."""
    print("[2/4] Cleaning graph (largest strongly-connected component)...")

    # Keep only the largest strongly connected component
    G_clean = ox.truncate.largest_component(G, strongly=True)

    print(f"       Cleaned graph: {G_clean.number_of_nodes()} nodes, "
          f"{G_clean.number_of_edges()} edges")
    return G_clean


def save_graphml(G, path: Path):
    """Save the graph in GraphML format for NetworkX interoperability."""
    print(f"[3/4] Saving GraphML -> {path}")
    ox.save_graphml(G, filepath=str(path))
    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"       Written {size_mb:.2f} MB")


def save_parquet_edgelist(G, path: Path):
    """Convert the graph to a GeoDataFrame edge list and save as Parquet."""
    print(f"[4/4] Saving Parquet edge list -> {path}")

    # osmnx provides a convenient converter
    gdf_edges = ox.graph_to_gdfs(G, nodes=False, edges=True)

    # Coerce columns with mixed types (list / scalar) to strings for Parquet.
    # OSM data frequently has list-valued fields (osmid, name, ref, etc.)
    for col in gdf_edges.columns:
        if col == "geometry":
            continue  # keep geometry native
        if gdf_edges[col].dtype == object:
            gdf_edges[col] = gdf_edges[col].astype(str)

    gdf_edges.to_parquet(str(path), engine="pyarrow", index=True)
    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"       Written {size_mb:.2f} MB  ({len(gdf_edges)} edges)")


def main():
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Download
    G = download_network((CENTER_LAT, CENTER_LNG), RADIUS_M, NETWORK_TYPE)

    # 2. Clean
    G = clean_graph(G)

    # 3. Save GraphML
    save_graphml(G, GRAPHML_PATH)

    # 4. Save Parquet edge list
    save_parquet_edgelist(G, PARQUET_PATH)

    # Summary
    print("\n[OK] Pipeline complete.")
    print(f"  GraphML : {GRAPHML_PATH}")
    print(f"  Parquet : {PARQUET_PATH}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\n[FAIL] Pipeline failed: {exc}", file=sys.stderr)
        sys.exit(1)
