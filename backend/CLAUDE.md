# CLAUDE.md — Backend (SUB-05)

Guidance for Claude Code (and any AI agent) working in the `backend/` directory of the
Urban Intelligence Platform. Read this before writing code here.

> [!IMPORTANT]
> **Git Branch Rule:** Pushing directly to the `main` branch is **STRICTLY PROHIBITED**.
> All active development, commits, and pushes must go to the **`dev` branch only**.
> Prior to executing any git commands or modifying files, you must load, read, and strictly adhere to `rule.md` in this directory.

> **Authority order (from PROJECT_SPEC §21):** `docs/PROJECT_SPEC (1).md` → `DECISIONS.md` →
> subsystem READMEs → inline comments. If they conflict, the higher one wins — flag the conflict,
> don't silently pick.

---

## 1. What this subsystem is

This is **SUB-05: Backend & API**, owned by Person 5, who is **also the integration / DevOps owner**.

The simulation core (SUB-01) produces state. The frontend (SUB-06) renders it. This backend is the
layer in between: it exposes sim state to the browser, accepts policy events back, and manages the
lifecycle of scenario runs. See `docs/ROLE_5_BACKEND.md` for the full role brief.

**One-line scope:** expose sim state via REST (snapshots/queries) and WebSocket (live ticks), inject
user events into the sim, manage scenario lifecycle (start/pause/reset/branch), and own CI + deploy.

## 2. The mental models that drive every decision here

These are from `docs/ROLE_5_BACKEND.md` — internalize them:

- **REST is for state; WebSocket is for streams.** Snapshots, scenario configs, and historical
  queries are REST. Live tick updates are streamed. Don't mix them.
- **The API is a contract.** Once the frontend depends on a field, you don't change it without
  coordination. Version the API (`/api/v1/...`). Keep the OpenAPI spec accurate.
- **Send the smallest thing that conveys the change.** Don't push a full city snapshot every tick —
  prefer diffs/aggregations. Full snapshots are a REST fetch, not a stream frame.
- **Backpressure is real.** If the sim ticks faster than the client renders, drop frames
  intelligently — never queue unboundedly.
- **Latency is felt; throughput is not.** A policy slider must register fast (≤ 1–2 ticks). Internal
  throughput is invisible to the user.
- **Monolith, not microservices,** at this scale. Clean internal modules over tiny coordinating services.

## 3. Tech stack (locked by PROJECT_SPEC §5.3)

| Concern | Choice | Notes |
|---|---|---|
| Framework | **FastAPI + uvicorn** | async, WebSocket support, auto OpenAPI |
| Streaming | **WebSockets** (`uvicorn[standard]`) | live tick fan-out |
| Wire format | **JSON** for v1 | MessagePack/Protobuf only if profiling demands it |
| State store | **in-process dict** for v1 | Redis only "if needed" — don't add it preemptively |
| Metadata | **SQLite** | scenario registry, run metadata. **No Postgres in v1.** |
| Sim outputs | **Parquet** | written by sim/data layers; backend reads when serving history |
| Validation/models | **Pydantic v2** | wire contracts live in `app/models/schemas.py` |
| Config | **pydantic-settings** | env-driven, see `app/config.py` |
| Tests | **pytest + httpx + pytest-asyncio** | API contract + smoke tests |
| Lint/format | **Ruff + Black**; type hints on public APIs | `mypy` encouraged |

**Do NOT introduce** (PROJECT_SPEC §5.3, §21): Postgres, Kubernetes, Kafka, microservices, Celery,
or new top-level dependencies — without first justifying them in `DECISIONS.md`.

> ⚠️ **Known divergence to resolve with the team:** the repo root `docker-compose.yml` and
> `.env.example` currently wire **Postgres + a Next.js frontend + an AI service with
> `ANTHROPIC_API_KEY`**. That contradicts the spec (SQLite, React/Vite, *no LLM at runtime* — §3.1,
> §4.3, §5.3). The backend in this folder follows the **spec**. Don't wire backend persistence to
> Postgres or call an LLM at runtime. Record the reconciliation in `DECISIONS.md`.

## 4. Hard constraints (PROJECT_SPEC §4.3 — non-negotiable)

- **No LLM calls anywhere in the request/tick path.** This backend serves a deterministic sim. If a
  task seems to ask for an LLM, push back and propose a rule-based/data alternative.
- **No proprietary paid datasets / paid APIs** without explicit authorization.
- Demo must run on a **single laptop**; total cloud spend for v1 demo **< ₹10,000**.

## 5. Directory layout

```
backend/
├── app/
│   ├── main.py            # app factory, lifespan (boots sim adapter + state store), router mount
│   ├── config.py          # Settings (env-driven via pydantic-settings)
│   ├── api/
│   │   ├── deps.py        # shared dependencies (get_state_store, get_scenario_manager)
│   │   └── routes/        # REST routers, one file per resource
│   │       ├── health.py        # /healthz, /readyz  (smoke-test target)
│   │       ├── scenarios.py      # CRUD + lifecycle: start/pause/resume/reset/branch
│   │       ├── snapshots.py      # GET current/by-tick snapshot (full state, REST)
│   │       ├── metrics.py        # GET aggregate metric time series
│   │       └── events.py         # POST policy/weather/infra events -> sim injection
│   ├── ws/
│   │   ├── manager.py     # ConnectionManager: register/unregister, fan-out, backpressure
│   │   └── stream.py      # /ws/scenarios/{id} live tick stream (diffs)
│   ├── store/
│   │   ├── state.py       # in-process StateStore (latest snapshot, ring buffer of ticks)
│   │   └── metadata.py    # SQLite scenario/run registry
│   ├── sim/
│   │   ├── adapter.py     # SimEngine Protocol — the seam to SUB-01
│   │   └── fake_engine.py # runnable stub so backend + frontend develop before SUB-01 lands
│   ├── services/
│   │   └── scenario_manager.py  # owns scenario lifecycle + the per-scenario tick loop task
│   └── models/
│       └── schemas.py     # ALL Pydantic wire contracts (the API contract lives here)
├── tests/
├── pyproject.toml
├── Dockerfile
├── .dockerignore
├── .env.example
└── README.md
```

## 6. The seam to the simulation core (SUB-01)

SUB-01 may not exist yet. The backend depends on the **`SimEngine` Protocol** in
`app/sim/adapter.py`, not on a concrete engine. `app/sim/fake_engine.py` is a deterministic stub
that emits plausible snapshots so the full vertical slice (data→sim→API→UI) is exercisable today.

When SUB-01 is ready, implement the same Protocol and swap it in via `Settings.sim_engine`
(`fake` | `mesa`). **Do not put sim logic in API handlers** (anti-pattern from the role brief) —
business logic belongs behind the adapter, in the sim layer.

Snapshot/event shapes are the contract — see `app/models/schemas.py`. Coordinate any change to
those shapes with SUB-01 (producer) and SUB-06 (consumer).

## 7. Conventions (PROJECT_SPEC §15)

- **API versioning:** all routes under `/api/v1`. WebSocket under `/ws`.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`).
- **Branches:** Pushing directly to the `main` branch is **STRICTLY PROHIBITED**. All changes must be pushed to the `dev` branch only, as defined in `rule.md`. Merge requests from `dev` to `main` should occur through pull requests.
- **IDs:** stable string IDs in serialized output (`scenario_0001`, `agent_00042`), not raw ints.
- **Units on the wire:** times UTC in storage / IST in display (frontend formats); currency as
  integer **paise** internally, formatted ₹ for display; coords WGS84 lat/lon.
- **Determinism:** a scenario is `config + seed`. Same request → same run. Echo the seed in responses.
- **Tests:** every route has a contract test; the WS stream has a smoke test. Keep `/healthz` and
  `/readyz` working — the daily integration smoke test hits them.

## 8. Integration / DevOps hat (you own this)

- **CI gate:** lint (Ruff) + type hints + `pytest` must pass before merge. Keep CI green; red CI for
  >1 day means the team stops trusting it.
- **Daily end-to-end smoke test:** boot backend (fake engine) → start a scenario → assert ticks
  stream → inject an event → assert effect. Wire it into CI on a schedule.
- **Deploy:** see `README.md` §Deployment. Target: local (`docker compose` / `uvicorn`) + optional
  Railway/Render for a public demo URL. A teammate must be able to deploy from scratch in < 30 min.

## 9. Local dev quickstart

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate   # Windows PowerShell
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload --port 8000
# OpenAPI docs: http://localhost:8000/docs
# Health:       http://localhost:8000/healthz
```

## 10. When in doubt

- Crossing into another subsystem? Surface the dependency; don't widen scope silently (§21).
- New dependency or architectural choice? Write it in `DECISIONS.md` first.
- API shape change? It's a contract change — coordinate with SUB-01 and SUB-06.
- Prefer the **simple** option. This codebase optimizes for student-team maintainability.
