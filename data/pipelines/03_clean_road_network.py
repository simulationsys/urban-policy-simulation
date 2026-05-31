#!/usr/bin/env python3
"""Clean and validate the road network from OSM.

Inputs:  data/raw/osm/delhi_network.graphml
Outputs: data/processed/road_network_delhi.parquet
         data/processed/road_network_delhi_stats.json
"""

import json
import sys
from pathlib import Path

try:
    import osmnx as ox
    import networkx as nx
    import pandas as pd
except ImportError:
    print("ERROR: osmnx, networkx, pandas required. Install with:")
    print("  pip install osmnx networkx pandas")
    sys.exit(1)

INPUT_FILE = Path(__file__).parent.parent / "raw" / "osm" / "delhi_network.graphml"
OUTPUT_DIR = Path(__file__).parent.parent / "processed"
OUTPUT_PARQUET = OUTPUT_DIR / "road_network_delhi.parquet"
OUTPUT_STATS = OUTPUT_DIR / "road_network_delhi_stats.json"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def clean_road_network():
    """Load, clean, and save the road network."""
    print("[03] Cleaning road network...")
    
    if not INPUT_FILE.exists():
        print(f"[03] ✗ ERROR: {INPUT_FILE} not found. Run 01_download_osm_delhi.py first.")
        return False
    
    try:
        # Load network
        print(f"  → Loading {INPUT_FILE}...")
        G = ox.load_graphml(str(INPUT_FILE))
        print(f"  → Initial: {len(G.nodes)} nodes, {len(G.edges)} edges")
        
        # Remove isolated nodes
        isolated = list(nx.isolates(G))
        if isolated:
            print(f"  → Removing {len(isolated)} isolated nodes...")
            G.remove_nodes_from(isolated)
        
        # Extract edges with attributes
        edges = []
        for u, v, key, data in G.edges(keys=True, data=True):
            edge = {
                "source": str(u),
                "target": str(v),
                "key": key,
                "length": data.get("length", 0),
                "highway": data.get("highway", "unclassified"),
            }
            edges.append(edge)
        
        df_edges = pd.DataFrame(edges)
        print(f"  → Extracted {len(df_edges)} edges")
        
        # Add inferred attributes
        def infer_speed(highway_type):
            """Infer speed by road type (km/h). Handle list values from OSM."""
            if isinstance(highway_type, list):
                highway_type = highway_type[0]  # Take first tag if list
            if not isinstance(highway_type, str):
                highway_type = "unclassified"  # Fallback
            
            speeds = {
                "motorway": 60,
                "trunk": 50,
                "primary": 40,
                "secondary": 30,
                "tertiary": 25,
                "residential": 15,
                "service": 10,
            }
            return speeds.get(highway_type, 20)
        
        def infer_capacity(highway_type):
            """Infer capacity (vehicles/hour/lane), assume 2 lanes. Handle list values."""
            if isinstance(highway_type, list):
                highway_type = highway_type[0]  # Take first tag if list
            if not isinstance(highway_type, str):
                highway_type = "unclassified"  # Fallback
            
            capacities = {
                "motorway": 2000,
                "trunk": 1800,
                "primary": 1500,
                "secondary": 1000,
                "tertiary": 600,
                "residential": 300,
                "service": 200,
            }
            base = capacities.get(highway_type, 500)
            return base * 2  # 2 lanes default
        
        df_edges["free_flow_speed_kmh"] = df_edges["highway"].apply(infer_speed)
        df_edges["capacity_veh_hr"] = df_edges["highway"].apply(infer_capacity)
        
        # Travel time in seconds (length in meters, speed in m/s)
        df_edges["free_flow_time_sec"] = (
            df_edges["length"] / (df_edges["free_flow_speed_kmh"] / 3.6)
        )
        
        # Convert highway to string for Parquet serialization
        df_edges["highway"] = df_edges["highway"].apply(
            lambda x: x[0] if isinstance(x, list) else (str(x) if x else "unclassified")
        )
        
        print(f"  → Inferred speeds and capacities")
        
        # Select clean columns for output
        df_out = df_edges[[
            "source", "target", "key", "length", "highway",
            "free_flow_speed_kmh", "capacity_veh_hr", "free_flow_time_sec"
        ]].copy()
        
        # Save as Parquet
        df_out.to_parquet(str(OUTPUT_PARQUET), index=False)
        print(f"  → Saved edge list to {OUTPUT_PARQUET}")
        
        # Save statistics
        stats = {
            "num_nodes": len(G.nodes),
            "num_edges": len(df_edges),
            "total_length_km": df_edges["length"].sum() / 1000,
            "highway_types": df_edges["highway"].value_counts().to_dict(),
            "avg_free_flow_speed_kmh": df_edges["free_flow_speed_kmh"].mean(),
        }
        with open(OUTPUT_STATS, "w") as f:
            json.dump(stats, f, indent=2)
        print(f"  → Saved statistics to {OUTPUT_STATS}")
        
        print("[03] ✓ Road network cleaning complete")
        print(json.dumps(stats, indent=2))
        return True
        
    except Exception as e:
        print(f"[03] ✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = clean_road_network()
    sys.exit(0 if success else 1)
