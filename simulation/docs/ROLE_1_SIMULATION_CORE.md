# ROLE 1 — Simulation Core Lead

> You are the physics engine of the city.

## The big picture

The simulation core is the heart of the project. Every other subsystem — agents, transport, data, dashboard — depends on you having built a stable, fast, deterministic substrate on which the world unfolds. If your subsystem is broken, nothing works. If your subsystem is slow, nothing impresses. If your subsystem is non-deterministic, nothing is reproducible — and reproducibility is what separates research from theater.

You are not building intelligence. You are building the **clock and the stage** on which intelligence performs.

## What you own

- The **simulation tick loop** — what happens every step, in what order
- The **world state** — the canonical representation of everything currently true about the city at this moment
- The **event system** — how internal events (rain starts, policy applied, metro line closed) propagate through the sim
- The **scheduler** — which agents and subsystems get to act on which ticks
- **Performance** — the sim must hit the team's tick-rate budget at the target population size
- **Determinism** — given a seed and a scenario config, a run reproduces exactly

## Mental models you need

**A simulation is a state machine, not a game loop.** Game engines aim for 60fps and tolerate non-determinism. You aim for reproducibility and aggregate correctness. These are different design goals — don't conflate them.

**Time is a budget.** Every subsystem wants to do something every tick. You decide who gets compute. Not every agent needs to act every tick; not every road segment needs updating at the same frequency. Build a scheduler that reflects this.

**State is centralized; logic is distributed.** The world state lives with you. Behavior logic lives with other subsystems. Be ruthless about this separation — it's what makes the system testable and what prevents subtle bugs where two modules silently disagree about reality.

**Vectorization beats parallelism for this kind of work.** A single NumPy operation over 10,000 agents is faster than 10,000 agents acting in a thread pool. Default to vectorized math over object-oriented agents wherever the logic permits. Reserve object orientation for cold, readable paths.

**Profile before optimizing.** Your intuition about what's slow will be wrong. Always.

## Key decisions you'll make

- **Tick granularity.** 1 minute? 5? 15? Trades realism against performance.
- **Continuous vs discrete time within a tick.** Mostly discrete is simpler; some operations (routing, event timing) want continuous resolution.
- **State storage layout.** Object-of-arrays (vectorizable, alien-looking) or array-of-objects (readable, slow). Often both — vectorize hot paths, keep readable cold paths.
- **Snapshot strategy.** Full state every tick or diffs only? Diffs are faster but harder to debug.
- **Agent activation policy.** Every tick, or scheduled based on the agent's next planned action?
- **How events are queued and applied** — at tick boundaries only, or mid-tick?

## Interfaces with other roles

- **Agent Behavior (Role 2)** queries world state from you; you receive their decisions and apply them
- **Transport (Role 3)** registers as a subsystem you tick each step; it updates network state
- **Backend (Role 5)** consumes your snapshots and injects events from the UI back into your event queue
- **Research (Role 7)** consumes your run outputs (snapshots, metrics, logs)

Define clean contracts for each interface. **These contracts are stable; what you do behind them is yours.**

## What "done" looks like

- The sim can run 7+ simulated days without crashing or memory blow-up
- A scenario config + seed produces an identical run twice in a row, byte-for-byte
- The sim hits the team's tick-rate target at the target population
- Other subsystems can register cleanly without rewriting your internals
- A teammate can read your loop code and understand it in 15 minutes

## Anti-patterns to avoid

- Hidden state in module globals
- Allowing agents to mutate other agents' state directly
- Mixing simulation time with wall-clock time anywhere except logging
- Optimizing before profiling
- Tight coupling between the loop and any specific subsystem's internals
- Putting domain logic (mode choice, congestion math) inside the engine

## Open questions you'll need to think through

- What's the canonical "current time" representation? Tick number? Sim-time datetime? Both?
- Where does the calendar (weekday, weekend, holidays) actually live — in the engine or in a subsystem?
- How do you handle agents that need to act outside their scheduled tick (event-driven response to a sudden rain start, for example)?
- What's the right way to pause/resume the sim for user interaction without breaking determinism?
- When the sim falls behind real-time playback rate, what gives — sim fidelity, render rate, or user-facing tick rate?

These don't have universally right answers. Reason about them in the context of the team's goals and write your decisions into `DECISIONS.md`.

## Where to look first

- The main `PROJECT_SPEC.md` — sections 3, 5, 8, 14, 16
- Existing ABM engines worth studying briefly: Mesa (Python, simple but slow), MATSim (Java, fast, complex), Agents.jl (Julia, fast). You're closest to Mesa in spirit, MATSim in ambition.
