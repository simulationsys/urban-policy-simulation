import geopandas as gpd
import json
import os
import random

def extract_rajiv_chowk():
    print("Loading data...")
    nodes_path = "../data/processed_data/nodes.parquet"
    edges_path = "../data/processed_data/edges.parquet"
    
    if not os.path.exists(nodes_path):
        print(f"File not found: {nodes_path}")
        return
        
    try:
        nodes_gdf = gpd.read_parquet(nodes_path)
        edges_gdf = gpd.read_parquet(edges_path)
    except Exception as e:
        print(f"Error reading parquet: {e}")
        return

    # Rajiv Chowk roughly: Lon 77.210 to 77.230, Lat 28.625 to 28.640
    print("Filtering using GeoPandas...")
    rc_edges = edges_gdf.cx[77.210:77.230, 28.625:28.640]
    rc_nodes = nodes_gdf.cx[77.210:77.230, 28.625:28.640]
    
    print(f"Found {len(rc_edges)} edges and {len(rc_nodes)} nodes in Rajiv Chowk.")
    
    out_path = "../frontend/public/rajiv_chowk_roads.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    rc_edges.to_file(out_path, driver="GeoJSON")
    print(f"Successfully wrote GeoJSON to {out_path}")
    
    # Generate mock 2D animated agents based on the extracted nodes
    agents = []
    
    # Extract coordinates from nodes to build random trips
    coords = []
    for geom in rc_nodes.geometry:
        if geom:
            coords.append((geom.x, geom.y))
            
    if len(coords) > 2:
        for i in range(150): # 150 2D agents
            start_coord = random.choice(coords)
            end_coord = random.choice(coords)
            agents.append({
                "id": f"agent_{i}",
                "type": random.choice(["car", "car", "car", "pedestrian"]),
                "start": [start_coord[1], start_coord[0]], # Leaflet expects [lat, lon]
                "end": [end_coord[1], end_coord[0]],
                "speed": random.uniform(0.0001, 0.0005) # degrees per frame roughly
            })
            
        with open("../frontend/public/rajiv_chowk_agents.json", "w") as f:
            json.dump(agents, f)
        print("Successfully wrote agents JSON.")

if __name__ == "__main__":
    extract_rajiv_chowk()
