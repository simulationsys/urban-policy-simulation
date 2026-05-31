# REQUIREMENTS — Phase 1 Real-City Simulation

> **Owner of this doc:** Person 1 (Simulation Core + Infra)  
> **Folders I own:** `simulation/`, `infra/`  
> **City:** New Delhi — Rajiv Chowk, 3–5 km radius (28.6328° N, 77.2197° E)  
> **Python:** 3.12 (pinned — osmnx/geopandas don't support 3.14)

---

## Current State of My Folders

### `simulation/` — What I've Already Built

| File | Lines | What It Does |
|---|---|---|
| `simulation/simulation/engine.py` | 310 | Mesa-backed `UrbanModel` + `MesaSimEngine` adapter. Tick loop, event dispatch, snapshot generation, 10×10 grid aggregation. |
| `simulation/simulation/network.py` | 484 | `MultiModalNetwork` — Delhi (Rajiv Chowk) 10×10 grid with roads, Yellow/Blue metro lines (DMRC), CP outer ring bus loop. Dijkstra routing, BPR congestion, routing cache. |
| `simulation/simulation/agents.py` | 353 | `CitizenAgent` — MNL mode choice, memory, schedule adaptation, advance-commute stepping. |
| `simulation/simulation/metrics.py` | 109 | `calculate_metrics()` — mode share, avg commute time, congestion index, metro load. |
| `simulation/simulation/__init__.py` | 8 | Public exports. |
| `simulation/tests/test_simulation.py` | 229 | 7 tests: init, stepping, events, determinism, routing cache, multi-modal routing, BPR calibration. |
| `simulation/pyproject.toml` | 24 | Deps: `mesa>=2.2`, `numpy`, `networkx`, `pandas`. |

> **Status:** Grid is now centered on Delhi Rajiv Chowk (28.6328, 77.2197) with Yellow/Blue DMRC metro lines. Still synthetic grid — will be swapped for real OSM data when data pipeline outputs are available.

### `infra/` — What Exists

| File | What |
|---|---|
| `infra/CLAUDE.md` | Agent guidance — Docker, CI/CD, K8s, Terraform scope |
| `infra/rule.md` | Git branch rules |
| `infra/agents/rules/rule.md` | AI agent rules for infra |

> **Status:** Empty scaffold. CI/CD and deployment are Phase 2 concerns per PROJECT_SPEC §13.

---

## What I Need From Each Role (Precise Deliverables)

---

### FROM SUB-04 — Data Engineering (Person 4)

> **Priority: 🔴 CRITICAL — I am blocked until these files exist.**

#### File 1: `data/processed_data/network.graphml`
- **Format:** GraphML (XML-based graph, loadable via `networkx.read_graphml()` or `osmnx.load_graphml()`)
- **Content:** OSM drivable road network, 4 km radius around Rajiv Chowk (28.6328, 77.2197) covering ~3–5 km study area. Cleaned to largest strongly-connected component.
- **Node schema:** `osmid (int64)` as node ID, attributes: `x (float, longitude)`, `y (float, latitude)`, `street_count (int)`
- **Edge schema:** `osmid`, `length (float, meters)`, `highway (str)`, `name (str)`, `geometry (WKT LineString)`
- **Why I need it:** My `MultiModalNetwork` must load a real road graph instead of the synthetic 8×8 grid. I will add a `load_from_osm()` classmethod.
- **Status:** Pipeline script exists at `data/pipelines/1_download_osm_network.py` but was **never run**. `processed_data/` is empty.

#### File 2: `data/processed_data/nodes.parquet`
- **Format:** GeoParquet (Parquet with geometry column)
- **Content:** Every road intersection node with its lat/lon coordinates
- **Schema:** Index: `osmid (int64)`. Columns: `x (float, lon)`, `y (float, lat)`, `street_count (int)`, `geometry (Point)`
- **Why I need it:** To assign agents to real intersection nodes; to compute distances; to build the visualization grid.
- **Status:** I already added `save_parquet_nodes()` to the pipeline script. Person 4 just needs to run it.

#### File 3: `data/processed_data/edges.parquet`
- **Format:** GeoParquet
- **Content:** Edge list with road attributes
- **Schema:** Multi-index: `(u, v, key)`. Columns: `osmid`, `length (m)`, `highway`, `name`, `geometry (LineString)`
- **Why I need it:** Alternative to GraphML for fast tabular loading; edge capacity estimation from `highway` classification.

#### File 4: `data/processed_data/metro_network.json`
- **Format:** JSON
- **Content:** Delhi Metro lines passing through the 3–5 km Rajiv Chowk zone
- **Why I need it:** To overlay metro stations + tracks onto the road graph in `MultiModalNetwork`
- **Schema I need:**
```json
{
  "lines": [
    {
      "name": "Yellow Line",
      "color": "#FFCC00",
      "stations": [
        {"name": "Chandni Chowk", "lat": 28.6567, "lon": 77.2315},
        {"name": "Rajiv Chowk", "lat": 28.6328, "lon": 77.2197},
        {"name": "Patel Chowk", "lat": 28.6226, "lon": 77.2138}
      ],
      "segments": [
        {"from": "Chandni Chowk", "to": "Rajiv Chowk", "travel_time_min": 3, "distance_km": 1.8},
        {"from": "Rajiv Chowk", "to": "Patel Chowk", "travel_time_min": 2, "distance_km": 1.1}
      ]
    }
  ]
}
```
- **Lines needed:** Yellow Line (at least 5 stations nearest to Rajiv Chowk), Blue Line (at least 5 stations nearest)
- **Can be hand-built** from DMRC website — no GTFS available.

#### File 5: `data/processed_data/bus_routes.json`
- **Format:** JSON
- **Content:** 5–10 major DTC bus routes passing through the study area
- **Why I need it:** To tag road edges with bus route IDs (like I currently do with `"ring_road"`)
- **Schema I need:**
```json
{
  "routes": [
    {
      "id": "DTC-423",
      "name": "Ambedkar Nagar to Old Delhi Rly Stn",
      "frequency_min": 15,
      "stops": [
        {"name": "Connaught Place", "lat": 28.6315, "lon": 77.2167},
        {"name": "Barakhamba Road", "lat": 28.6330, "lon": 77.2280}
      ]
    }
  ]
}
```

#### File 6: `data/processed_data/weather_delhi.csv`
- **Format:** CSV
- **Content:** Daily rainfall + temperature for Delhi, at least one monsoon season (Jun–Sep)
- **Schema:** `date, rainfall_mm, temp_max_c, temp_min_c, humidity_pct`
- **Why I need it:** To drive Scenario A (Monsoon Stress Test). My engine currently has `weather_rain_intensity` as a float 0–1; I need a mapping from actual rainfall mm to this intensity.
- **Source:** IMD open data or OpenWeather historical API.

#### File 7: `data/processed_data/synthetic_population.parquet`
- **Format:** Parquet
- **Content:** 10,000 agent records assigned to real OSM node IDs
- **Schema I need:**
```
agent_id          int64       unique
home_node         int64       real OSM node ID from nodes.parquet
work_node         int64|null  real OSM node ID (null for non-workers/retired)
age               int
income_bracket    int (1-5)
household_id      int
occupation        str         office_executive|student|blue_collar_worker|gig_worker|retired_citizen
has_car           bool
has_bike          bool
has_metro_pass    bool
```
- **Why I need it:** My `UrbanModel._generate_synthetic_population()` currently assigns agents to random grid nodes. I need a `_load_real_population()` path that reads this file.
- **Depends on:** Files 1, 2 must exist first (real node IDs needed).

#### File 8: `data/validation/mode_share_delhi.csv`
- **Format:** CSV
- **Schema:** `mode, share_pct, source, year`
- **Why I need it:** To calibrate agent utility weights so simulated mode share matches reality.

#### File 9: `data/validation/dmrc_ridership.csv`
- **Format:** CSV
- **Schema:** `station, daily_ridership, peak_hour_ridership, source, year`
- **Why I need it:** Validation anchor — is my metro load metric in the right ballpark?

---

### FROM SUB-02 — Agent Behavior / AI (Person 2)

> **Priority: 🟡 MEDIUM — their code works in isolation, needs integration into my engine.**

#### What they have that I need:
Their agent behavior stack in `ai/sim/agents/` is more advanced than my `simulation/simulation/agents.py`:
- 5 Indian occupational archetypes (vs my generic demographics)
- Household car-sharing mutex
- Multi-leg activity schedules (vs my simple home↔work)
- Frustration-driven mode switching
- Per-occupation utility weights

#### What I need from them:

| # | Deliverable | Why |
|---|---|---|
| 1 | **Merge their `Occupation` enum + archetype weights into my `agents.py`** | My agents don't have occupational archetypes. Their `UtilityWeights.for_occupation()` is ready. |
| 2 | **Merge their `Household` car-sharing logic** | My agents don't share cars. Their `Household.request_car()` / `release_car()` pattern is clean. |
| 3 | **Merge their `ActivitySchedule` multi-leg tour system** | My agents only do home→work→home. Their schedule supports Home→School→Work→Shopping→Home. |
| 4 | **Merge their `AgentMemory` frustration tracking** | My memory is `list[dict]`. Theirs is a proper `AgentMemory` with `frustration_by_mode` and `habit_bonus()`. |
| 5 | **Refactor their `population.py` to use real OSM node IDs** | Their `build_population()` uses `rng.integers(0, n_nodes)`. Must accept real node IDs from SUB-04. |

> **Decision needed:** Do we merge their code INTO `simulation/simulation/agents.py`, or do we make `simulation/` import from `ai/sim/agents/`? Keeping one canonical location avoids drift.

---

### FROM SUB-05 — Backend (Person 5)

> **Priority: 🟢 LOW for now — already integrated.**

#### What already works:
- `backend/app/models/schemas.py` defines `ScenarioConfig`, `Snapshot`, `GridCell`, `AggregateMetrics`, `Event`, `EventType`
- My `MesaSimEngine` already satisfies the `SimEngine` protocol
- My `engine.py` imports from `app.models.schemas`

#### What I need from them:

| # | Deliverable | Why |
|---|---|---|
| 1 | **Add `use_real_data: bool` to `ScenarioConfig`** | So I can switch between synthetic grid and real OSM data via config |
| 2 | **Add `network_paths: dict` to `ScenarioConfig`** | Paths to `network.graphml`, `metro_network.json`, `bus_routes.json` |
| 3 | **Add `population_path: str | None` to `ScenarioConfig`** | Path to `synthetic_population.parquet` |

---

### FROM SUB-06 — Frontend (Person 6)

> **Priority: 🟢 LOW — they consume my snapshots, I don't depend on them.**

#### What they need from me (for their reference):
- `Snapshot` object with `grid: list[GridCell]` (lat, lon, density, congestion)
- `AggregateMetrics` with mode_share, avg_commute, metro_load, congestion_index
- WebSocket stream from backend

#### What I need from them:
Nothing for Phase 1. They consume my output.

---

### FROM SUB-07 — Research (Person 7)

> **Priority: 🟡 MEDIUM — needed for calibration.**

| # | Deliverable | Why |
|---|---|---|
| 1 | **`research/experiments/anchors.yaml`** — Formal anchor metric definitions | I need to know what values my simulation should hit. |
| 2 | **Calibration feedback** — "Your mode share is X%, real is Y%, adjust β_cost" | I tune utility weights based on their analysis. |

---

## What I Must Deliver (My Own Checklist)

### `simulation/` Changes for Phase 1

| # | File | Change | Depends On |
|---|---|---|---|
| 1 | `simulation/simulation/network.py` | Add `MultiModalNetwork.load_from_osm(graphml_path, metro_json, bus_json)` classmethod. Keep synthetic grid as fallback. | SUB-04 files 1, 4, 5 |
| 2 | `simulation/simulation/network.py` | Update `CITY_LAT`/`CITY_LON` constants → Delhi (28.6328, 77.2197) when real data mode | SUB-04 file 1 |
| 3 | `simulation/simulation/engine.py` | Add `_load_real_population(parquet_path)` alongside existing `_generate_synthetic_population()` | SUB-04 file 7 |
| 4 | `simulation/simulation/engine.py` | Add config flag to switch real vs synthetic data | SUB-05 `ScenarioConfig` update |
| 5 | `simulation/simulation/agents.py` | Merge SUB-02's occupation archetypes, household sharing, multi-leg schedules | SUB-02 code review |
| 6 | `simulation/scenarios/baseline_delhi.yaml` | **NEW** — Default scenario config for Delhi | All data files |
| 7 | `simulation/pyproject.toml` | Add `osmnx`, `geopandas`, `pyarrow` to dependencies | Python 3.12 |
| 8 | `simulation/tests/test_real_data.py` | **NEW** — Tests that load real GraphML and verify routing works | SUB-04 file 1 |

### `infra/` — Phase 1 Scope

| # | File | What |
|---|---|---|
| 1 | `docker-compose.yml` (root) | Already exists. Verify backend + frontend services work together. |
| 2 | `infra/scripts/setup_env.sh` | **NEW** — One-command dev environment setup (create venvs, install deps, run data pipeline) |
| 3 | `.github/workflows/ci.yml` | **NEW** (when ready) — Run `pytest simulation/tests/` on PR |

---

## Python Dependencies — All Roles

### `simulation/requirements.txt` (my folder)
```txt
# Core simulation
mesa>=2.2.0
numpy>=1.24.0
networkx>=3.2
pandas>=2.0.0

# Real data loading (Phase 1)
osmnx>=1.9.0
geopandas>=0.14
pyarrow>=15.0

# Dev
pytest>=8.0
black>=24.0
ruff>=0.5
mypy>=1.10
```

### `data/requirements.txt` (Person 4 — for reference)
```txt
osmnx>=1.9.0
geopandas>=0.14
pandas>=2.1
shapely>=2.0
networkx>=3.2
pyarrow>=15.0
requests>=2.31
```

### `ai/requirements.txt` (Person 2 — for reference)
```txt
numpy>=1.26
pandas>=2.1
scipy>=1.11
pyarrow>=15.0
# Dev
pytest>=8.0
black>=24.0
ruff>=0.5
mypy>=1.10
```

### `backend/requirements.txt` (Person 5 — for reference)
```txt
fastapi>=0.115
uvicorn[standard]>=0.30
pydantic>=2.7
pydantic-settings>=2.3
websockets>=12.0
# Dev
pytest>=8.0
pytest-asyncio>=0.23
httpx>=0.27
ruff>=0.5
```

### `frontend/package.json` additions (Person 6 — for reference)
```json
{
  "dependencies": {
    "maplibre-gl": "^4.0.0",
    "chart.js": "^4.4.0"
  }
}
```

### `research/requirements.txt` (Person 7 — for reference)
```txt
jupyter>=1.0
matplotlib>=3.8
pandas>=2.1
pyarrow>=15.0
geopandas>=0.14
```

---

## Environment Setup

```bash
# Python 3.12 is required (osmnx has no wheels for 3.14)
# After installing Python 3.12:

# Simulation (my folder)
cd simulation
py -3.12 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
pytest tests/

# Verify
python -c "import mesa; import networkx; print('simulation deps OK')"
```

---

## Dependency Graph — Who Blocks Whom

```
DATA ENGINEER (Person 4) ← CRITICAL PATH
  │
  ├─ network.graphml ──────► ME (network.py load_from_osm)
  ├─ nodes.parquet ────────► ME (population assignment)
  ├─ metro_network.json ───► ME (overlay metro onto graph)
  ├─ bus_routes.json ──────► ME (overlay bus onto graph)
  ├─ weather_delhi.csv ────► ME (monsoon scenario driver)
  ├─ synthetic_population.parquet ► ME (engine._load_real_population)
  └─ validation CSVs ──────► RESEARCH (Person 7) ──► ME (calibration feedback)

AI AGENT (Person 2)
  └─ Advanced agent code ──► ME (merge into simulation/simulation/agents.py)

BACKEND (Person 5)
  └─ ScenarioConfig updates ► ME (config flag for real vs synthetic)

ME (Simulation Core)
  └─ Snapshot stream ──────► BACKEND ──► FRONTEND
```
