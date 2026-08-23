# Architectural Decision Log (DECISIONS.md)

This log tracks key architectural and design decisions for the **Urban Intelligence Platform (Pravaah)**.

---

## ADR 001: Frontend Architecture & Visual Core (SUB-06)

### Context
We need to scaffold the visual subsystem for `SUB-06` (Frontend & Infographics) to surface the underlying agent-based simulation telemetry. The specification mandates strict TypeScript (`TypeScript: Strict mode. ESLint + Prettier`), high responsiveness, a non-generic premium visual aesthetic (avoiding out-of-the-box Material UI/Bootstrap frameworks), and high-density, legible visual telemetry representing thousands of active simulated commuters under weather/flood stress.

### Options Considered
1. **Option A: React + Vite + TailwindCSS + Radix/lucide**:
   - *Pros*: Extremely rich ecosystem, standard in current industry web apps.
   - *Cons*: Introduces heavy virtual DOM overhead, bloats npm dependencies, runs risks of default look/style fatigue, and complicates canvas synchronization.
2. **Option B: Vanilla TypeScript + Vite + Modular Custom HSL CSS + Native Canvas overlay (Chosen)**:
   - *Pros*: Extreme high performance (natively compiles to a tiny static bundle in milliseconds), complete absolute freedom in custom CSS without utility restrictions, pixel-level canvas render control running at 60 FPS, zero third-party bloated libraries, perfectly maps to the strict custom typography guidelines.
   - *Cons*: Requires manually setting up DOM linkages, event handling, and custom graphing utilities.

### Decision
We chose **Option B (Vanilla TypeScript + Vite + Modular HSL CSS + Native HTML5 Canvas particle system)**.

### Consequences
- **Ultra-lightweight footprint**: The production bundle measures less than 40KB (HTML, JS, and CSS combined!), loading instantly on any device.
- **Flawless 60 FPS Animating Overlays**: Demonstrates thousands of commuters dynamically flowing across concentric-radial networks using native Canvas animations, bypassing React diffing overheads.
- **Built-in Mock Sandbox Fallback**: Provides a self-contained local tick emulator that fully functions offline/without standard databases, allowing instant demo validation, while smoothly reconnecting to WebSocket streams if the FastAPI backend goes live.
- **Clean modularity**: Easily scalable CSS variables file `variables.css` acting as the absolute source of truth for typography and theme.

> **Note (superseded in part):** the shipped dashboard in `frontend/` is Next.js + React +
> deck.gl + Mapbox, not the Vanilla TS/Canvas stack described above. The rendering decisions
> that actually govern the current map are ADR 006 and ADR 007.

---

## ADR 002: Streaming Individual Agents to the Map (SUB-01 → SUB-05 → SUB-06)

### Context
The Mesa engine simulates households, activity schedules, mode choice and memory, but none of
that reached the browser. `TickDiff` carried only aggregate metrics and grid cells, so the map
fell back to `frontend/public/rajiv_chowk_agents.json` — 150 routes between *randomly chosen*
OSM nodes. The dashboard therefore showed traffic that responded to nothing: the policy sliders
changed the numbers while the vehicles drove the same canned loops.

A tick is 5 simulated minutes. At that granularity a car covers several hundred metres, so
streaming one position per tick would teleport every vehicle between frames.

### Options Considered
1. **Per-tick positions for every agent**: simple, but teleports on every frame and violates
   PROJECT_SPEC §16.1 ("don't render every agent") at population scale.
2. **Keep aggregating to grid cells only**: cheap and already built, but no individual is ever
   visible, so "watch one citizen" is impossible.
3. **Stream journey *legs* for a bounded cohort (Chosen)**: send the routed polyline plus the
   engine's own travel-time estimate once, when a leg starts; the client animates along it
   using simulated time.

### Decision
We stream **legs, not positions** (`AgentLeg`), plus `AgentPresence` for agents that are
stationary and `Dwelling` for their homes. The number of individually streamed agents is capped
by `ScenarioConfig.max_tracked_agents` (default 2,000); everyone beyond the cap still drives the
simulation and appears in the aggregate grid.

### Consequences
- Motion is continuous: the client interpolates simulated time between ticks, deriving the clock
  rate by measuring the gap between ticks rather than assuming the server's interval.
- A leg is sent once, and its id once it ends, so steady-state frames stay small.
- A client connecting mid-run would have missed everything, so `/ws` now opens with a
  **bootstrap frame** shaped exactly like a tick, carrying the full current world.
- Grid cells remain the only population-scale channel, honouring PROJECT_SPEC §16.1.

---

## ADR 003: Engine Selection is Automatic, and Says So

### Context
`Settings.sim_engine` defaulted to `"fake"` in both `config.py` and `.env.example`, so the
deployed backend served the stub: analytic metrics, zero simulated citizens. Nothing in the API
or the UI distinguished that from a real run, and the frontend silently fell back to canned
routes — the failure looked exactly like a working city.

The backend Docker image also copied only `app/`, with none of the `simulation` package or its
dependencies, so `BACKEND_SIM_ENGINE=mesa` could not have worked in a container regardless.

### Options Considered
1. **Flip the default to `mesa`**: fails hard wherever the simulation package is absent.
2. **Keep `fake` and document the override**: preserves the silent-failure trap.
3. **`auto`, with the live engine reported over the API (Chosen)**.

### Decision
`sim_engine` defaults to **`auto`**: the backend *imports* `simulation.engine` (not merely
locating it — `find_spec` proves the file exists, not that mesa/pandas are installed), checks for
processed data, and picks accordingly, logging the reason at boot. `/readyz` reports `engine`,
`real_data` and `simulates_individuals`, and the dashboard shows a
**"DEMO PLAYBACK — NOT SIMULATED"** banner whenever no citizens are being simulated.

### Consequences
- A fresh checkout with data present runs the real engine on real streets with no configuration.
- Explicit `fake` / `mesa` still override, so CI and slim deployments are unaffected.
- The banner also triggers on ground truth — several ticks arrived carrying no citizens — so it
  works against older backends that do not report an engine at all.
- `backend/Dockerfile` now builds from the **repository root** and bundles `simulation/` and
  `data/processed_data`. Building from `backend/` alone yields a stub-only image.
- Scenario rows left as `running` by a previous process are reconciled to `paused` at boot,
  since the in-process engines are gone.

---

## ADR 004: Routing Performance — A* and a Split Cache

### Context
With 5,000 agents on the real ~7,000-node Delhi network, a rush-hour tick took **15.5 s**,
against the PROJECT_SPEC §16.2 budget of 1 tick/second. The cost was where §16.1 predicted:
route queries. `find_shortest_path` ran `nx.dijkstra_path` with a Python weight callback,
relaxing most of the graph on every query.

`update_road_congestion` also called `clear_routing_cache()` **every tick**, so the
"high-performance routing cache" never survived long enough to be reused.

### Options Considered
1. **Precompute many-to-one paths** (§16.1's suggestion): large memory, and origins change daily.
2. **Rewrite the router as a compiled extension**: outside v1 scope (§16.3 says profile first).
3. **A\* with an admissible heuristic, plus keeping static-cost routes cached (Chosen)**.

### Decision
Route with **A\***, using straight-line distance divided by the fastest speed that mode can ever
achieve — congestion, rain and mode-mixing only make a leg slower, so the bound never
overestimates and paths stay optimal. Congestion-sensitive modes (car, auto, e-rickshaw) keep a
separate cache dict cleared each tick in O(1); walk/bike/bus/metro routes persist across ticks.

### Consequences
- Rush hour at 5,000 agents: **15.5 s → ~5.2 s per tick**; at 1,200 agents, **1.5 s**.
- Verified optimal: across 100 queries over five modes, no A\* path was worse than Dijkstra's.
- The cache split is *correct* but was **not** the win — with thousands of agents over 7,000
  nodes almost every origin–destination pair is unique, so hit rates stay low. Recorded here so
  the next person does not re-investigate it.
- Still above the 1 tick/s budget at full population. The honest remaining lever is fewer or
  cheaper route queries, not micro-optimisation.

---

## ADR 005: Homes, Household Activity, and the Working City

### Context
Agents vanished from the map the moment they arrived anywhere, so outside the peaks the city
looked deserted. The engine also spawns stall owners, store managers, shop staff and delivery
riders — roughly 10% of the population — none of which were ever serialized.

### Decision
- Every citizen gets a **`Dwelling`** derived from their income bracket: jhuggi (14 m²), chawl
  room (32 m²), walk-up flat (62 m²), apartment (115 m²), bungalow (260 m²), each with a room
  list. The distribution is the census-derived population's, not an invented one.
- A **household routine** covers the day in 18 bands with three variants each, filtered by wealth
  and occupation and phase-shifted per agent, so a street does not cook dinner in unison.
- Economic agents are streamed as `AgentPresence` with a `role` and a `detail` map carrying their
  commercial state (stock, cash, deliveries, bankruptcy).

### Consequences
- The map is populated around the clock, and the working city is visible for the first time.
- Spectating a citizen at home opens their dwelling into a labelled floor plan, and they stand in
  the room their current chore belongs to.
- **Names are the one thing the engine does not model.** They are generated deterministically
  from the agent id and the UI says so; age, occupation, household and trade all come from the
  simulation. Nothing invented is presented as simulated.
- The population parquet stores OSM node ids, which go stale when the network is rebuilt. The
  loader repairs dangling references and reports how many, instead of failing mid-tick.

---

## ADR 006: Rendering — Level of Detail Over the Base Map

### Context
Drawing 1,200 dwellings and 1,320 agents as extruded geometry at every zoom buried the Mapbox
base map, which already renders Delhi's real buildings and streets. The result read as a rash of
coloured blocks rather than a city.

### Decision
The base map is the city; deck.gl adds the people to it. Detail is revealed by zoom: traffic at
any zoom (with a minimum pixel size so vehicles stay legible in a wide shot), workplaces from
z14.5, residents from z16, homes/footpaths/trees from z17. Homes are culled to ~450 m around the
camera (cap 250) plus whoever is being followed. Layers that duplicate the base map (roads,
footpaths, parks) are subdued and gated behind their overlay toggle.

### Consequences
- Wide shots stay readable; street level is full of life. A legend dims whatever the current zoom
  is hiding, so an empty-looking view explains itself.
- 3D models are optional: `.glb` files are verified by magic bytes at startup (a static host that
  answers 404 with `index.html` returns HTTP 200, which looks like success), and the map falls
  back to procedural geometry at true vehicle dimensions if any is missing.
- deck.gl reconciles layers by id, so each variant (model vs procedural) uses its own layer id —
  reusing one id across layer types applies the old accessors to the new type and breaks it.

---

## ADR 007: Vehicles Follow Street Geometry, Not Intersection Chords

### Context
Vehicles drove through buildings. The engine routes over the OSM graph, whose nodes are
intersections; the map joined them with straight lines, discarding the shape of the street
between. **7,414 of 17,594 edges (42%) are curved** — Connaught Place is concentric circles, so a
chord across an arc passes through everything inside it.

Measured lateral error of a chord against the real street: median 1.8 m, 90th percentile 26.7 m,
99th 110.7 m, worst **384.8 m**. On **33.7% of curved edges** a vehicle strayed more than 5 m
off-road. A second, self-inflicted cause: the polyline cap sampled vertices at even intervals,
which is blind to where the bends are.

### Decision
Each road edge stores its real OSM geometry (`shape`), and a leg's polyline is built by walking
those shapes, reversing a way's geometry when travel runs against the direction OSM recorded it.
The vertex cap uses **corner-preserving simplification** — drop the vertices deviating least from
the chord between their neighbours — so straight runs shed points and curves keep them.

### Consequences
- Polyline length against true road length: **1.0% mean error → 0.1%**. Routes trace the street at
  ~16 m median vertex spacing.
- Payload grew, so coordinates are rounded to 6 decimals (~11 cm, finer than a lane): bootstrap
  **1663 KB → 519 KB**, per leg **4.6 KB → 3.76 KB**.
- Peak ticks still reach 200–290 KB when ~50 agents depart at once. Acceptable locally; the next
  lever for a public deployment is lowering the 400-vertex cap.
