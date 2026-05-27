# Backend & API (SUB-05)

The REST + WebSocket layer of the Urban Intelligence Platform. It exposes simulation state to the
dashboard, accepts policy events back, and manages scenario lifecycle. Owned by Person 5, who is
also the **integration / DevOps owner**.

- Role brief: [`docs/ROLE_5_BACKEND.md`](docs/ROLE_5_BACKEND.md)
- Project spec: [`docs/PROJECT_SPEC (1).md`](<docs/PROJECT_SPEC (1).md>)
- AI-agent guide for this folder: [`CLAUDE.md`](CLAUDE.md)/


sarthak gaandu

> **v1 runs against a stub simulation** (`app/sim/fake_engine.py`) so the full data→sim→API→UI slice
> works before SUB-01 lands. Swap in the real engine by implementing the `SimEngine` Protocol in
> `app/sim/adapter.py` and setting `BACKEND_SIM_ENGINE=mesa`.

## Stack

FastAPI · uvicorn · WebSockets · Pydantic v2 · SQLite (metadata) · in-process state store. JSON on
the wire. No Postgres, no LLM at runtime — both are hard constraints from the spec (§4.3, §5.3).

## Quickstart (local, no Docker)

```powershell
cd backend
& "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe" -m venv .venv   # or your python
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

- Swagger / OpenAPI docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/healthz>

### Try the full loop

```bash
# 1. Create a scenario
curl -X POST http://localhost:8000/api/v1/scenarios \
  -H "content-type: application/json" \
  -d '{"config":{"name":"scenario_a_monsoon","city":"bengaluru","population":10000,"seed":42}}'

# 2. Start it  (use the id returned above, e.g. scenario_0001)
curl -X POST http://localhost:8000/api/v1/scenarios/scenario_0001/start

# 3. Stream live ticks
#    (any WS client) ws://localhost:8000/ws/scenarios/scenario_0001

# 4. Inject the monsoon mid-run
curl -X POST http://localhost:8000/api/v1/scenarios/scenario_0001/events \
  -H "content-type: application/json" \
  -d '{"type":"WEATHER_EVENT","payload":{"rain_intensity":0.9,"duration_ticks":60}}'

# 5. Add 20% bus capacity (the Scenario A intervention)
curl -X POST http://localhost:8000/api/v1/scenarios/scenario_0001/events \
  -H "content-type: application/json" \
  -d '{"type":"POLICY_EVENT","payload":{"bus_capacity_pct":1.2}}'
```

## API surface (v1)

| Method | Path | Purpose |
|---|---|---|
| GET | `/healthz`, `/readyz` | liveness / readiness (smoke-test targets) |
| GET | `/api/v1/scenarios` | list scenarios |
| POST | `/api/v1/scenarios` | create scenario from config + seed |
| GET | `/api/v1/scenarios/{id}` | scenario detail |
| POST | `/api/v1/scenarios/{id}/start\|pause\|resume\|reset` | lifecycle |
| POST | `/api/v1/scenarios/{id}/branch` | fork into a new scenario |
| DELETE | `/api/v1/scenarios/{id}` | delete |
| GET | `/api/v1/scenarios/{id}/snapshot[/{tick}]` | full world state (REST) |
| GET | `/api/v1/scenarios/{id}/metrics?from_tick&to_tick` | aggregate time series |
| POST | `/api/v1/scenarios/{id}/events` | inject weather/policy/infra event |
| WS | `/ws/scenarios/{id}` | live tick diffs; also accepts inbound events |

**REST is for state; WebSocket is for streams.** Full snapshots and history are REST; per-tick diffs
are streamed. The OpenAPI spec at `/openapi.json` is the contract the frontend consumes — keep it
accurate.

## Tests & lint

```powershell
pytest -q          # contract + WS smoke tests
ruff check .       # lint
black .            # format
```

`tests/test_ws.py` is the shape of the **daily end-to-end smoke test**: boot → create → start →
assert ticks stream → inject event.

## Project layout

See [`CLAUDE.md`](CLAUDE.md) §5 for the annotated directory map. In short:
`app/api/routes` (REST) · `app/ws` (stream + fan-out) · `app/store` (in-process state + SQLite) ·
`app/services/scenario_manager.py` (lifecycle + tick loop) · `app/sim` (the seam to SUB-01) ·
`app/models/schemas.py` (the wire contract).

---

# Deployment — what to deploy where, and how

The spec's constraints decide this for us: **demo must run on a single laptop**, **total cloud spend
< ₹10,000**, no DevOps-heavy infra (§4.3, §5.3). So there are two tiers.

## Tier 1 — Local (always works, zero cost, the demo fallback)

Everything runs on one laptop. This is the **primary demo target** and the deterministic fallback if
conference Wi-Fi dies (§17 risk: "Demo network fails → always have a recorded/local fallback").

```bash
# from repo root, once the frontend Dockerfile exists
docker compose up --build
# or run pieces directly:
#   backend:  uvicorn app.main:app --port 8000   (in backend/)
#   frontend: npm run dev                         (in frontend/)
```

> ⚠️ The repo-root `docker-compose.yml` currently includes `db` (Postgres) and an `ai` service.
> Per the spec the backend uses **SQLite, not Postgres**, and there is **no runtime AI service**.
> Reconcile this with the team and record it in `DECISIONS.md`. The backend image here needs neither.

## Tier 2 — One public demo URL (optional, for credibility)

Recommended split — each piece goes where it's cheapest and simplest:

| What | Where | Why |
|---|---|---|
| **Backend (this service)** | **Railway** (or Render) | Free/cheap tier, native WebSocket support, `$PORT` auto-injected, deploys straight from the `Dockerfile` here. Render's free tier sleeps and drops WS connections — fine for a casual demo, annoying for a live one; Railway's hobby plan stays warm. |
| **Frontend (React/Vite)** | **Vercel** or **Netlify** | Free static hosting + global CDN. Build `frontend/`, set `VITE_API_URL` / `VITE_WS_URL` to the backend URL. |
| **Heavy sim training (v2 only)** | a spot VM, only when needed | Not for v1. The live demo runs the engine inside this backend process. |

There is **no database to host** (SQLite is a file in the container) and **no AI service to host**.
That keeps you well under the ₹10,000 budget — realistically ₹0 on free tiers.

### Deploy the backend to Railway (≈10 minutes)

1. Push the repo to GitHub (CI must be green — see below).
2. Railway → **New Project → Deploy from GitHub repo**, set **Root Directory = `backend`**.
   Railway detects the `Dockerfile` and builds it.
3. Set environment variables (Railway → Variables):
   ```
   BACKEND_ENVIRONMENT=production
   BACKEND_CORS_ORIGINS=https://<your-frontend>.vercel.app
   BACKEND_SIM_ENGINE=fake        # switch to mesa when SUB-01 ships
   BACKEND_TICK_INTERVAL_SECONDS=1.0
   ```
   Don't set `BACKEND_PORT` — the container honors Railway's injected `$PORT`.
4. (Optional) Add a **Volume** mounted at `/app/data` so the SQLite scenario registry survives
   redeploys. Live tick buffers are in-memory and reset on restart by design.
5. Note the public URL, e.g. `https://uip-backend.up.railway.app`. The frontend points at it
   (`https://...` for REST, `wss://...` for the WebSocket).

Render is the same shape: **New → Web Service**, root `backend`, Docker runtime, same env vars; it
also injects `$PORT`.

### WebSocket gotchas (read before the demo)

- Use **`wss://`** (not `ws://`) against an HTTPS backend, or browsers block the connection.
- CORS must list the **exact** frontend origin in `BACKEND_CORS_ORIGINS` (scheme + host, no path).
- On Render's free tier the service sleeps after inactivity and the WS drops — hit `/healthz` to wake
  it, or use Railway / a paid Render instance for a live demo.

## CI / integration (your DevOps hat)

A GitHub Actions workflow lives at [`../.github/workflows/backend-ci.yml`](../.github/workflows/backend-ci.yml):
on every PR touching `backend/` it runs **ruff + pytest**. Keep it green — red CI for >1 day and the
team stops trusting it (ROLE_5 anti-pattern). The pytest WS test doubles as the daily smoke test;
wire it to a scheduled run once the stack is deployed.

**"Done" for deployment:** a teammate can go from clone to a running stack by following this section
in under 30 minutes (ROLE_5 definition of done).
