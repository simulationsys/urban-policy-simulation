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

See [docs/](docs/) for detailed setup and architecture.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file.
