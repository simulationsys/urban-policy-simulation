# Changes Log — Role 2 (SUB-02 Agent Behavior)

> Tracks all updates made by Role 2 on the Urban Intelligence Platform.
> Branch: `role-2/agent-behavior-scaffold`

---

## 2026-06-01 — Retail & Economic Agent Behavior Expansion

### Summary
Implemented a comprehensive economic and retail behavioral model under SUB-02 to simulate interactions between formal retail (shops), informal retail (roadside stalls), and citizen shoppers. The platform now supports multi-day retail micro-simulation, spatial foot traffic evaluations, perishable inventory decay, weather/eviction disruptions, and formal shift staffing with schedule synchronisation.

### New components and files (new)
| File | Purpose |
|---|---|
| [sim/agents/retail_memory.py](sim/agents/retail_memory.py) | `RetailMemory` tracking rolling daily sales outcomes, moving averages, and frustration metrics [0.0, 5.0]. |
| [sim/agents/stall_owner.py](sim/agents/stall_owner.py) | `StallOwner` base and subclasses (`FoodStallOwner`, `ClothesStallOwner`, `AccessoriesStallOwner`) with foot-traffic based relocation, pricing, inventory decay, and disruption risks. |
| [sim/agents/store_agents.py](sim/agents/store_agents.py) | `StoreManager` (inventory restocking, shift allocation) and `StoreStaff` (commute-bound schedule, late-arrival frustration). |
| [sim/agents/shop_choice.py](sim/agents/shop_choice.py) | `ShopChoiceModel` (MNL discrete choice) for shopper agent destination choice (Formal vs. Informal) with Gumbel-max utility selection. |
| [sim/agents/retail_interaction.py](sim/agents/retail_interaction.py) | Transaction processing engine `process_purchase` updating shopper utility and stall/store memory states dynamically. |
| [sim/tests/test_retail_agents.py](sim/tests/test_retail_agents.py) | Comprehensive test suite containing 9 tests validating stall lifecycle, relocation, store manager shift logic, and purchase updates. |
| [sim/scripts/demo_shopping.py](sim/scripts/demo_shopping.py) | Rich, interactive 5-part demo script simulating shoppers, stall relocation, shift delays, and purchase updates over multi-day iterations. |

### Integrations and Modifications
- **[sim/agents/modes.py](sim/agents/modes.py)** — Added `STALL_OWNER`, `STORE_MANAGER`, `STORE_STAFF` to `Occupation` enum.
- **[sim/agents/schedule.py](sim/agents/schedule.py)** — Added `VENDING` activity type to `ActivityType` enum.
- **[sim/agents/agent.py](sim/agents/agent.py)** — Added `shopping_needs` list to the base `Agent` model using lazy-loading import guards to avoid circular references.
- **[sim/agents/__init__.py](sim/agents/__init__.py)** — Exposed all new classes and utility methods publicly.

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
