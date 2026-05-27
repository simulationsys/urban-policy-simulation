# Changes Log — Role 2 (SUB-02 Agent Behavior)

> Tracks all updates made by Role 2 on the Urban Intelligence Platform.
> Branch: `role-2/agent-behavior-scaffold`

---

## 2026-05-27 — Initial scaffold

### Summary
Set up the foundation for the SUB-02 Agent Behavior module per `PROJECT_SPEC.md` §6–7. The module now has a working agent data model, a multinomial-logit mode-choice engine, rolling memory, and a passing test suite.

### Project setup (new)
- **[pyproject.toml](pyproject.toml)** — Python 3.11+ project config
  - Runtime deps: `numpy`, `pandas`, `scipy`
  - Dev deps: `pytest`, `black`, `ruff`, `mypy`
  - `mypy --strict` enabled on `sim/`
  - Black + Ruff line length 100, per spec §15.1
- **[.gitignore](.gitignore)** — ignores `__pycache__`, venvs, caches, `data/raw/`, `data/processed/`, `*.parquet`, editor folders.

### Agent behavior module (new) — `sim/agents/`
| File | Purpose |
|---|---|
| [sim/agents/modes.py](sim/agents/modes.py) | `Mode` enum: walk, bike, bus, metro, auto, car |
| [sim/agents/agent.py](sim/agents/agent.py) | `Agent` dataclass + `AgentState` (matches spec §7.1) |
| [sim/agents/memory.py](sim/agents/memory.py) | `AgentMemory` rolling window per mode + `CommuteOutcome`; computes `habit_bonus` |
| [sim/agents/schedule.py](sim/agents/schedule.py) | `ActivitySchedule` — daily leave/return times with jitter |
| [sim/agents/mode_choice.py](sim/agents/mode_choice.py) | `ModeChoiceModel` (multinomial logit), `UtilityWeights`, `ModeAlternative` |
| [sim/agents/__init__.py](sim/agents/__init__.py) | Public exports |

### Utility function (spec §7.2)
```
U(mode) = β_time*time + β_cost*cost*income_scale
        + β_comfort*comfort + β_weather*weather_penalty
        + β_habit*habit_bonus + ε   (ε ~ Gumbel)
```
- Income-scaled cost sensitivity (lower bracket → higher cost weight)
- Gumbel noise → equivalent to softmax-sampled MNL
- Default weights are textbook starting points; **must be calibrated** later against city mode-share data

### Tests (new) — `sim/tests/`
- [sim/tests/test_agents_smoke.py](sim/tests/test_agents_smoke.py) — 4 tests, all passing:
  1. `available_modes` respects bike/car ownership
  2. `AgentMemory.habit_bonus` accounting
  3. Deterministic choice prefers faster mode
  4. Rain shifts agent off exposed modes (bike → metro)

### Documentation (new)
- [docs/subsystems/SUB-02.md](docs/subsystems/SUB-02.md) — module overview, utility-function description, deliberate non-inclusions, dev commands.

### Git
- New branch: `role-2/agent-behavior-scaffold`
- Commit: `feat(sub-02): scaffold agent behavior module` (14 files, +1398)
- Remotes:
  - `origin` → `https://github.com/shubhamahuja9999/urban-policy-simulation.git` (fork)
  - `upstream` → `https://github.com/simulationsys/urban-policy-simulation.git`
- PR draft URL: <https://github.com/shubhamahuja9999/urban-policy-simulation/pull/new/role-2/agent-behavior-scaffold>

---

## Deliberately deferred (not yet built)

These are out of scope for the initial scaffold and tracked here so they aren't forgotten:

- **Per-agent heterogeneous utility weights** — waiting on SUB-04's synthetic population schema before sampling weights per income bracket.
- **Household / joint decisions** — single-agent decisions only for now.
- **Activity-based scheduling beyond home↔work** — discretionary trips, multi-leg tours.
- **Schedule adaptation** — "three bad commutes → leave earlier" loop from spec §7.3.
- **Calibration pass** — needs anchor metrics (spec §11.1) once city is chosen.
- **RL hooks** — per spec §3.1 and the role doc, RL is reserved for system-level optimisation (e.g. signal timing) and is not part of mode choice.

---

## Next steps (suggested order)

1. Wait for Role 1 to define the `Agent.observe / decide / act` interface the tick loop calls; wire `ModeChoiceModel` into it.
2. When SUB-04 publishes the synthetic-population schema, add `sim/agents/population.py` to build N agents from a DataFrame and sample per-agent weights.
3. Implement schedule adaptation (memory-driven leave-time shift).
4. First calibration pass once a city and anchor metrics are picked.
