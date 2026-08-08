import osmnx as ox
import os

print("Starting OSMnx processing for Rajiv Chowk Buildings 800m...")
center_point = (28.6328, 77.2197)
dist = 800

try:
    buildings = ox.features_from_point(center_point, tags={'building': True}, dist=dist)
    parks = ox.features_from_point(center_point, tags={'leisure': 'park'}, dist=dist)
    
    print(f"Found {len(buildings)} buildings and {len(parks)} parks.")
    
    bldg_out = "../frontend/public/rajiv_chowk_buildings.json"
    park_out = "../frontend/public/rajiv_chowk_parks.json"
    
    buildings.to_file(bldg_out, driver="GeoJSON")
    parks.to_file(park_out, driver="GeoJSON")
    print("Exported Vector Models successfully.")
    
except Exception as e:
    print(f"Error downloading features: {e}")
