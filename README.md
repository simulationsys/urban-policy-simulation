# Urban Policy Simulation

A platform for modeling, simulating, and evaluating the impact of urban policy decisions
(zoning, transit, housing, taxation, environmental rules) before they are enacted.

## Overview

Urban Policy Simulation lets planners, researchers, and policymakers define policy
scenarios, run agent-based and statistical simulations over real city data, and explore
projected outcomes through an interactive interface — augmented by AI for scenario
generation and result explanation.

## Repository Structure

| Directory     | Purpose                                                                 |
| ------------- | ----------------------------------------------------------------------- |
| `frontend/`   | Web UI for building scenarios and visualizing simulation results.       |
| `backend/`    | API server, auth, scenario persistence, and orchestration.             |
| `simulation/` | Core simulation engine (agent-based / system-dynamics models).         |
| `ai/`         | AI services: scenario generation, result explanation, calibration.     |
| `data/`       | Datasets, ingestion pipelines, and schemas for city data.              |
| `docs/`       | Architecture, API, and user documentation.                             |
| `research/`   | Papers, notebooks, and experimental modeling work.                     |
| `infra/`      | Infrastructure-as-code, CI/CD, and deployment manifests.               |
| `shared/`     | Code, types, and constants shared across services.                     |

## Getting Started

```bash
# Copy environment template and fill in values
cp .env.example .env

# Start the full stack
docker-compose up --build
```

> The backend image builds from the **repository root** (`docker build -f backend/Dockerfile .`)
> because it has to contain the simulation core and its processed data. An image built from
> `backend/` alone can only ever run the stub engine.

### Running it locally with the real simulation

```bash
# 1. Build the Delhi street network + census-derived population (once, ~20s)
python data/pipelines/run_all.py
```

```bash
# 2. Backend — PYTHONPATH makes the simulation core importable
cd backend && PYTHONPATH=../simulation uvicorn app.main:app --port 8000
```

```bash
# 3. Frontend — point NEXT_PUBLIC_BACKEND_URL at the backend, then:
cd frontend && npm run dev
```

**Check what you are actually watching.** The engine is chosen automatically and reported at
`/readyz` and in the boot log. If the dashboard shows an amber **"DEMO PLAYBACK — NOT SIMULATED"**
banner, the backend is running the stub: the vehicles on the map are pre-recorded routes and no
citizen is being simulated. See `backend/README.md` for the engine table.

### What you can see once it is running

- Individual citizens routed along **real streets**, choosing between walking, cycling, bus,
  metro, auto, e-rickshaw and car — with the whole population underneath as a density grid.
- Each citizen's **home**, sized by what their income affords, from a jhuggi to a bungalow.
- **Household life**: click someone at home to watch the day's chores, or step inside to a
  labelled floor plan where they stand in the room the chore belongs to.
- The **working city**: stall owners, shopkeepers, shop staff and delivery riders, with their
  stock, takings and deliveries.
- Detail is revealed as you zoom in; a legend shows what the current zoom is hiding.

Architectural decisions — including why legs rather than positions are streamed, and why
vehicles follow street geometry — are recorded in [DECISIONS.md](DECISIONS.md).

See [docs/](docs/) for detailed setup and architecture.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file.
