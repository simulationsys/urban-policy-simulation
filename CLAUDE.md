# CLAUDE.md - Global AI Agent Context

Guidance for Claude Code (and any AI agent) working in this repository. Read this before writing code.

> [!IMPORTANT]
> **Git Branch Rule:** Pushing directly to the `main` branch is **STRICTLY PROHIBITED**.
> All active development, commits, and pushes must go to the **`dev` branch only**.
> Prior to executing any git commands or modifying files, you must load, read, and strictly adhere to the `rule.md` file in the current working directory.

## Subsystem Architecture Overview
- **`frontend/`**: Web UI for building scenarios and visualizing results (React/Vite).
- **`backend/`**: FastAPI API server, WebSocket stream server, metadata store (SQLite), and simulation adapter.
- **`simulation/`**: Core simulation engine (agent-based modeling).
- **`ai/`**: Scenario generation, result explaining, and offline calibration models.
- **`data/`**: Ingestion pipeline and data storage for urban metrics.
- **`shared/`**: Common types and schema declarations.
- **`infra/`**: Docker configs and deployment manifests.

## Key Developer Commands (Root)
- Start the entire stack: `docker-compose up --build`
- Setup environment: Copy `.env.example` to `.env`
