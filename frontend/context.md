# Urban Policy Simulation: Project Context & Architecture

This document provides a comprehensive overview of the technical implementations, data pipelines, and visual physics engines that power the Urban Policy Simulation dashboard. It is written to onboard new developers and explain the current state of the application from scratch.

## 1. Core Architecture & Mapping
The frontend is built on a modern **Next.js** stack utilizing **Deck.gl** and **Mapbox (React Map GL)** for high-performance WebGL data visualization. 
- We completely stripped away the default Google Maps POI clutter in favor of a sleek, minimalist base map. This ensures that the simulation data (vehicles, pedestrians, and roads) remains the absolute visual focal point.
- The map supports rich 3D perspective rendering, allowing users to zoom in and track individual vehicles navigating the city.

## 2. Geospatial Data Pipeline (OSMnx)
To make the simulation geographically accurate, we built a Python data extraction pipeline (`backend/simulation/data/extract_vector_world.py`) that queries real-world map data using **OSMnx**.
- **Segregated Networks:** We extract two completely independent topological graphs: a `drive` network for vehicles and a `walk` network for pedestrians. This mathematically prevents cars from driving through parks or on sidewalks.
- **Path Resampling:** Raw OpenStreetMap geometries can be jagged. We use `shapely.geometry.LineString` to mathematically resample the road paths into smooth, evenly spaced 2-meter coordinate vectors, ensuring silky-smooth animation in the frontend.
- **Traffic Light Extraction:** We specifically filter the OSMnx nodes for `highway='traffic_signals'` to extract real-world intersection coordinates. These coordinates are slightly offset diagonally by ~5 meters so that the 3D traffic light models sit perfectly on the street corners rather than in the middle of the road.

## 3. Agent Simulation & Physics Engine
The actual movement of vehicles is calculated in real-time on the frontend within `DashboardMap.tsx` using a custom JS physics engine.
- **Routing:** Agents are pre-routed in the backend using `networkx` shortest-path algorithms and fed to the frontend as coordinate arrays.
- **Collision Avoidance:** Vehicles continuously monitor the distance to other vehicles. To prevent infinite traffic jams (deadlocks), we implemented a vector dot-product check. A vehicle will only hit the brakes if the other vehicle is mathematically *in front* of its forward heading vector.
- **Traffic Light Logic:** Traffic lights run on a globally synced 3-second phase cycle (Red -> Yellow -> Green). Vehicles dynamically calculate their proximity to intersection nodes and will accurately brake and queue up if the light phase is Red or Yellow, only proceeding on Green.

## 4. Procedural 3D Models
Instead of using low-poly generic blobs, we wrote a generative 3D modeling script (`generate_colored_models.py`) using the `trimesh` Python library to procedurally build custom `.glb` assets.
- **Models:** 
  - Cars: Crimson Red Sedans with dark windows.
  - Buses: Long Schoolbus-Yellow city transit buses.
  - Pedestrians: Detailed 3D stick-figures (blue torso, skin-tone head, dark pants).
  - Traffic Lights: Vertical dark-grey poles with a black box and 3 distinct bulbs.
- **GLTF Baking:** Deck.gl's `ScenegraphLayer` is very particular about GLTF node hierarchies. To prevent visual glitches (like traffic light bulbs detaching and floating on the road), the Python script mathematically fuses all vertices and bakes the vertex colors directly into a single unified mesh before exporting.
- **Orientation:** The `ScenegraphLayer` applies dynamic yaw rotations based on the agent's path heading, ensuring vehicles face perfectly down the road.

## 5. Urban Policy Controls
The dashboard features an interactive **Congestion Fee** slider. As the user increases the fee, the frontend dynamically filters out a deterministic percentage of the vehicle agents from the rendering loop. This creates an immediate visual representation of how aggressive road pricing successfully clears urban traffic jams.
