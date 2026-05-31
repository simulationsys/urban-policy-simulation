#!/usr/bin/env python3
"""Download OSM data for Delhi using OSMnx.

Output: data/raw/osm/delhi_network.graphml
        data/raw/osm/delhi_bounds.geojson
"""

import json
import sys
from pathlib import Path

try:
    import osmnx as ox
    import geopandas as gpd
except ImportError:
    print("ERROR: osmnx and geopandas required. Install with:")
    print("  pip install osmnx geopandas")
    sys.exit(1)

OUTPUT_DIR = Path(__file__).parent.parent / "raw" / "osm"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

GRAPHML_FILE = OUTPUT_DIR / "delhi_network.graphml"
BOUNDS_FILE = OUTPUT_DIR / "delhi_bounds.geojson"


def download_osm_delhi():
    """Download road network for 4km radius around Rajiv Chowk."""
    print("[01] Downloading OSM road network (4km radius around Rajiv Chowk)...")
    
    try:
        # Rajiv Chowk coordinates (central Delhi)
        center_lat, center_lon = 28.6328, 77.2197
        radius_meters = 4000  # 4 km (average of 3-5 km range)
        
        # Download road network
        print(f"  → Downloading road network...")
        G = ox.graph_from_point(
            (center_lat, center_lon),
            dist=radius_meters,
            network_type="all",
            simplify=True,
            retain_all=False,
            truncate_by_edge=True,
        )
        print(f"  → Network: {len(G.nodes)} nodes, {len(G.edges)} edges")
        
        # Save as GraphML
        ox.save_graphml(G, filepath=str(GRAPHML_FILE))
        print(f"  → Saved to {GRAPHML_FILE}")
        
        # Save bounds as GeoJSON (compute from graph nodes)
        node_lats = [data['y'] for _, data in G.nodes(data=True)]
        node_lons = [data['x'] for _, data in G.nodes(data=True)]
        bbox = [min(node_lats), min(node_lons), max(node_lats), max(node_lons)]
        
        bounds = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [bbox[1], bbox[0]],  # SW
                    [bbox[1], bbox[2]],  # NW
                    [bbox[3], bbox[2]],  # NE
                    [bbox[3], bbox[0]],  # SE
                    [bbox[1], bbox[0]],  # close ring
                ]]
            },
            "properties": {
                "name": "Delhi OSM Boundary",
                "bbox": bbox,
            }
        }
        with open(BOUNDS_FILE, "w") as f:
            json.dump(bounds, f, indent=2)
        print(f"  → Saved bounds to {BOUNDS_FILE}")
        
        print("[01] ✓ OSM download complete")
        return True
        
    except Exception as e:
        print(f"[01] ✗ ERROR: {e}")
        return False


if __name__ == "__main__":
    success = download_osm_delhi()
    sys.exit(0 if success else 1)
