# Agent Rules

This document defines the rules and protocols for agents operating within the `simulation` domain of the project.

## Push & Code Integration Rules

1. **Direct Pushes Prohibited**: No agent is allowed to push commits directly to any branch, especially `main` or `master`.
2. **Pull Requests Only**: All modifications, updates, or additions must be submitted via Pull Requests (PRs).
3. **Target Branch**: All Pull Requests created by the agent MUST target the `dev` branch of the repository.
4. **Local CI Validation**: Before creating or updating a Pull Request, the agent MUST run the local CI checks to ensure the pipeline will not fail. For example, for the `backend` directory, this includes running code formatting tools (`black`), linting tools (`ruff check`), and the test suite (`pytest -q`).
