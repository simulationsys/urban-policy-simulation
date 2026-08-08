import osmnx as ox
import networkx as nx
import json
import random
import os
import shapely.geometry
import numpy as np

def generate_vector_world():
    print("Starting OSMnx processing for Rajiv Chowk...")
    center_point = (28.6328, 77.2197)
    dist = 1750  # 1.75km radius = 3.5km diameter area
    
    # 1. Download Graph for Routing
    print("Downloading street network...")
    # Get all drivable roads, but manually remove service roads later
    G_drive = ox.graph_from_point(center_point, dist=dist, network_type='drive', simplify=True)
    G_walk = ox.graph_from_point(center_point, dist=dist, network_type='walk', simplify=False)
    
    # Remove service roads from drive graph manually so we don't accidentally remove link roads!
    edges_to_remove = []
    for u, v, k, data in G_drive.edges(keys=True, data=True):
        hw = data.get('highway', '')
        if isinstance(hw, list):
            if 'service' in hw: edges_to_remove.append((u, v, k))
        elif hw == 'service':
            edges_to_remove.append((u, v, k))
    G_drive.remove_edges_from(edges_to_remove)
    
    print(f"Downloaded drive graph with {len(G_drive.nodes)} nodes and walk graph with {len(G_walk.nodes)} nodes.")
    
    # 1.5 Export Roads and Walk GeoJSON
    print("Exporting road network GeoJSON...")
    nodes_gdf, edges_gdf = ox.graph_to_gdfs(G_drive)
    edges_out = "../../frontend/public/rajiv_chowk_roads.json"
    os.makedirs(os.path.dirname(edges_out), exist_ok=True)
    # Simplify for Leaflet/DeckGL
    edges_gdf.reset_index()[['geometry']].to_file(edges_out, driver="GeoJSON")
    print(f"Exported roads successfully to {edges_out}.")
    
    nodes_w_gdf, edges_w_gdf = ox.graph_to_gdfs(G_walk)
    walk_out = "../../frontend/public/rajiv_chowk_walk.json"
    edges_w_gdf.reset_index()[['geometry']].to_file(walk_out, driver="GeoJSON")
    print(f"Exported walk network successfully to {walk_out}.")
    
    # 2. Generate Agent Paths
    print("Calculating realistic shortest-path routes...")
    agents = []
    
    for i in range(150):
        try:
            agent_type = random.choice(["car", "car", "car", "car", "bus", "pedestrian"])
            G = G_walk if agent_type == "pedestrian" else G_drive
            nodes = list(G.nodes)
            
            start_node = random.choice(nodes)
            end_node = random.choice(nodes)
            if start_node == end_node:
                continue
            
            # Get shortest path
            path = nx.shortest_path(G, start_node, end_node, weight='length')
            path_length = nx.shortest_path_length(G, start_node, end_node, weight='length')
            
            # Convert node IDs to coordinates, including edge geometry
            coords_path = []
            for idx in range(len(path)-1):
                u = path[idx]
                v = path[idx+1]
                edge_data = G.get_edge_data(u, v)
                data = edge_data[0] if 0 in edge_data else list(edge_data.values())[0]
                
                if 'geometry' in data:
                    # Follow the actual curve of the road
                    for lon, lat in data['geometry'].coords:
                        coords_path.append([lat, lon]) # Leaflet format
                else:
                    # Fallback to straight line between nodes
                    if idx == 0:
                        coords_path.append([G.nodes[u]['y'], G.nodes[u]['x']])
                    coords_path.append([G.nodes[v]['y'], G.nodes[v]['x']])
                    
            if len(coords_path) > 1:
                # Resample coords_path into perfectly equally spaced segments (approx 2 meters)
                # This ensures the frontend physics engine moves the car at a strictly constant speed!
                line = shapely.geometry.LineString(coords_path)
                if line.length > 0:
                    spacing_deg = 2.0 / 111139.0
                    distances = np.arange(0, line.length, spacing_deg)
                    if len(distances) == 0 or distances[-1] != line.length:
                        distances = np.append(distances, line.length)
                    coords_path = [list(line.interpolate(distance).coords)[0] for distance in distances]
                
            if len(coords_path) > 1:
                # Calculate progress per frame based on real-world speed
                # 60 frames per second
                # Cars/buses ~ 8-12 m/s (30-40 km/h)
                # Pedestrians ~ 1.4 m/s (5 km/h)
                physical_speed = 1.4 if agent_type == "pedestrian" else random.uniform(8.0, 12.0)
                progress_per_frame = (physical_speed / 60.0) / max(path_length, 1.0)
                
                agents.append({
                    "id": f"agent_{i}",
                    "type": agent_type,
                    "path": coords_path,
                    "speed": progress_per_frame
                })
        except nx.NetworkXNoPath:
            continue
                
        out_agents = "../../frontend/public/rajiv_chowk_agents.json"
        os.makedirs(os.path.dirname(out_agents), exist_ok=True)
        with open(out_agents, "w") as f:
            json.dump(agents, f)
        print(f"Exported {len(agents)} routed agents.")

    # 2.5 Extract Traffic Lights
    print("Extracting traffic light intersections...")
    traffic_lights = []
    for node, data in G_drive.nodes(data=True):
        if 'highway' in data and data['highway'] == 'traffic_signals':
            traffic_lights.append({
                "id": f"tl_{node}",
                "position": [data['x'], data['y']]
            })
    
    out_tl = "../../frontend/public/traffic_lights.json"
    with open(out_tl, "w") as f:
        json.dump(traffic_lights, f)
    print(f"Exported {len(traffic_lights)} traffic lights.")

    # 3. Download Buildings & Parks
    print("Downloading buildings and parks...")
    try:
        buildings = ox.features_from_point(center_point, tags={'building': True}, dist=dist)
        parks = ox.features_from_point(center_point, tags={'leisure': 'park'}, dist=dist)
        
        print(f"Found {len(buildings)} buildings and {len(parks)} parks.")
        
        # Export to GeoJSON
        bldg_out = "../../frontend/public/rajiv_chowk_buildings.json"
        park_out = "../../frontend/public/rajiv_chowk_parks.json"
        
        buildings.to_file(bldg_out, driver="GeoJSON")
        parks.to_file(park_out, driver="GeoJSON")
        print("Exported Vector Models successfully.")
        
    except Exception as e:
        print(f"Error downloading features: {e}")

if __name__ == "__main__":
    generate_vector_world()
