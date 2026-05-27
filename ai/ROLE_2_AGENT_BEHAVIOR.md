# ROLE 2 — Agent Behavior + AI

> You make the citizens feel like people.

## The big picture

If the simulation core is the stage, you write what the actors do on it. You decide how a citizen of the city wakes up, chooses how to get to work, reacts when it rains, learns from yesterday's bad commute, and shifts behavior over time. The realism of the entire simulation rests on whether the population, in aggregate, behaves like a real city — even though no individual agent is doing anything sophisticated.

This is the role most likely to be misunderstood as "build a smart AI for each citizen." That instinct is wrong, and it's important you internalize why early. A real city's intelligence doesn't come from each person being a genius — it comes from millions of simple decisions interacting under shared constraints. Your job is to design those simple decisions well enough that emergent behavior looks plausible.

## What you own

- **The agent data model** — what attributes every citizen carries
- **The decision logic** — how an agent chooses among modes, routes, departure times, whether to make a trip at all
- **The activity schedule system** — when does each agent move, and why
- **Adaptation and memory** — how agents update preferences based on outcomes
- **Behavioral diversity** — making sure not every agent behaves identically
- **Where (and where not) to use machine learning** in the agent stack

## Mental models you need

**Most agent decisions are utility-based, not learned.** The canonical method here is discrete choice modeling (multinomial logit and its variants). An agent scores each option using a utility function over time, cost, comfort, and habit; picks the best (with some noise). This is a half-century-old technique from transport economics and it works.

**Reinforcement learning is a precision tool, not the default.** RL is useful for things that genuinely benefit from learning a policy over time — traffic signal timing, fleet dispatching, emergency routing. RL is the wrong tool for "what mode does this person take to work today." The reason: training cost, opaqueness, and the fact that we have decades of well-calibrated discrete choice models that already work. Use RL where it earns its keep; use utility/rules everywhere else.

**Emergence is engineered, not summoned.** "Emergent behavior" sounds magical but it's the result of feedback loops you deliberately wire up. Bad commute → memory updates → next-day decision shifts → aggregate mode share moves. If you don't build the loops, nothing emerges. If you build them, behavior changes in interesting and sometimes surprising ways.

**Aggregate validity matters more than individual realism.** Nobody will check whether agent #47291's choice today was "correct." People will check whether the city's overall mode share matches reality. Optimize for the aggregate; individual variation is a means, not an end.

**Heterogeneity is the cheapest realism.** Two agents with identical utility weights produce a boring sim. Distribute weights across the population (sampled from sensible distributions) and the system feels alive without any additional cleverness.

## Key decisions you'll make

- What attributes does an agent need? (Income, age, household, vehicle ownership, schedule type, more?)
- What's the utility function's shape? Start with a textbook MNL — what extensions matter for our scenarios?
- How are utility weights distributed across the population? Single value with noise, or sampled per income bracket?
- How do agents represent memory? Last N commutes? Exponential moving average? Something richer?
- When (if ever) does an RL component enter the stack? For which behaviors specifically?
- How do you handle joint decisions (a household deciding together) vs individual decisions?

## Interfaces with other roles

- **Simulation Core (Role 1)** schedules you, gives you world state, receives your decisions
- **Transportation (Role 3)** gives you route options and travel time estimates; your decisions create the demand
- **Data Engineering (Role 4)** gives you the synthetic population — you decide what attributes that population needs
- **Research (Role 7)** validates your aggregate outputs against real mode share / commute time data and tells you when your weights need tuning

## What "done" looks like

- Agents produce a mode share that matches the calibration target within agreed bounds
- Agents respond visibly to environmental change (rain, congestion, policy) in plausible directions
- Behavior diversifies across the population without scripted exceptions
- A behavioral change (new policy, new mode) can be added without rewriting the decision engine
- An outsider can read your utility function and understand what it represents

## Anti-patterns to avoid

- Using an LLM to "make agents smarter" — this is a hard constraint, not a style preference
- Giving every agent the same utility weights
- Hardcoded if-else trees for every scenario (this won't scale)
- Letting agents access the global world state without going through the engine's interfaces
- Training reinforcement learning models before the baseline behaves correctly without learning
- Reasoning about agents one at a time when the calibration question is always aggregate

## Open questions you'll need to think through

- How much memory should an agent carry? Realism says weeks; performance says days.
- Should agents have personalities (risk-averse, status-conscious) or just demographic profiles?
- How do you bootstrap the agent's first day, when they have no memory yet?
- Where does social influence sit — do agents observe each other's choices, or only their own outcomes?
- For RL components: what's the reward signal, what's the state, and what's the action space?

## Where to look first

- The main `PROJECT_SPEC.md` — sections 3, 7, 11
- Ben-Akiva & Lerman, *Discrete Choice Analysis* — the canonical reference for how to think about agent decisions
- Any paper using the term "activity-based travel demand model" — that's the framework you're working in
