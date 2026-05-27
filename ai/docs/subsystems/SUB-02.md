# SUB-02 — Agent Behavior

Owner: Role 2. See `PROJECT_SPEC.md` §6 (SUB-02) and §7 for canonical scope.

## Modules

- `sim/agents/agent.py` — `Agent` dataclass, `AgentState` enum.
- `sim/agents/modes.py` — `Mode` enum (walk, bike, bus, metro, auto, car).
- `sim/agents/memory.py` — `AgentMemory`, `CommuteOutcome`. Rolling window of past commute outcomes per mode; produces `habit_bonus`.
- `sim/agents/schedule.py` — `ActivitySchedule`. Stylised daily timing with jitter.
- `sim/agents/mode_choice.py` — `ModeChoiceModel` (multinomial logit) and `UtilityWeights`. The decision function from §7.2.

## Utility function (current)

```
U(mode) = β_time*time + β_cost*cost*income_scale
        + β_comfort*comfort + β_weather*weather_penalty
        + β_habit*habit_bonus + ε   (ε ~ Gumbel)
```

Defaults in `UtilityWeights` are textbook starting points and **must be calibrated** against the chosen city's mode-share data (§11).

## What is intentionally not here yet

- Population-level heterogeneity (per-agent weight sampling) — needs synthetic population from SUB-04 first.
- Household joint decisions.
- Activity-based scheduling beyond home↔work.
- RL hooks. Per §3.1 and the role doc, RL is reserved for system-level optimisation, not per-agent mode choice.

## Dev

```
pip install -e ".[dev]"
pytest
ruff check sim
mypy sim
```
