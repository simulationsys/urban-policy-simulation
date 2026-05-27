# ROLE 5 — Backend + APIs

> You are the nervous system of the project — and its integration owner.

## The big picture

The simulation produces state. The frontend renders state. Without you, those two never meet. You build the layer that exposes the sim to the outside world, accepts commands back, and keeps the experience responsive enough that users believe they're watching a living city rather than a delayed log file.

You also have a second hat that the role title doesn't fully capture: **you are the integration owner**. With seven people pushing to one repository, the difference between a project that ships and one that collapses in week 6 is whether someone owns the seams. That someone is you. Your subsystem touches every other subsystem, which means you're the natural place for CI, deployment, and end-to-end smoke testing to live.

## What you own

- The **API surface** the frontend talks to — endpoints, contracts, versioning
- The **streaming layer** — how live sim state reaches the browser
- The **event injection path** — how user actions become events the sim consumes
- **Scenario lifecycle** — starting, pausing, resetting, branching simulation runs
- **State serialization** — turning the sim's internal world into wire-format messages
- **Integration health** — daily end-to-end smoke tests, CI, deployment
- **API documentation** — frontend and external consumers must be able to read and understand the contract

## Mental models you need

**REST is for state; WebSocket is for streams.** Snapshots, scenario configs, and historical queries are RESTful. Live tick updates are streamed. Confusing the two leads to either a chatty UI hammering REST or a stream carrying data that should have been a one-time fetch.

**The API is a contract, not an implementation detail.** Once the frontend depends on a field, changing that field without coordination is a betrayal. Version your API. Document it. Treat it like an interface to a different company even though that company is sitting next to you.

**Send the smallest thing that conveys the change.** A full city snapshot every tick is bandwidth suicide and CPU pressure on the frontend. Diffs, aggregations, and zoom-dependent payloads keep things smooth.

**Backpressure is real.** If the sim ticks faster than the frontend can render or the network can carry, you need to drop frames intelligently, not queue forever. Plan for this before it bites.

**Latency is felt; throughput is not.** Users notice when a policy slider takes 800ms to register. They don't notice that the sim is internally running 3x faster than the UI shows. Optimize for perceived responsiveness over raw throughput.

**Microservices are usually the wrong answer at this scale.** A monolith with clean internal modules is easier to reason about, deploy, and debug than five tiny services that have to coordinate. Defer the microservice instinct until you have a concrete reason it's needed.

## Key decisions you'll make

- REST vs WebSocket boundaries — what belongs where?
- Snapshot format — full state vs deltas, JSON vs binary (MessagePack, Protobuf)?
- How to handle scenario branching — does the user run multiple sims in parallel, or one at a time?
- Authentication — does the demo need any? (Probably not for v1, but think about it.)
- Deployment target — local-only, or a public demo URL?
- How long do completed scenario runs live in storage? Forever? 7 days?
- CI gating — what tests must pass before a PR can merge?

## Interfaces with other roles

- **Simulation Core (Role 1)** is your data source — you pull snapshots from them, push events to them
- **Frontend (Role 6)** is your most demanding consumer — they will discover every bug in your API contract
- **Research (Role 7)** may consume your historical scenario data for offline analysis
- **Everyone** depends on your CI being green and your daily smoke test passing

## What "done" looks like

- The frontend can subscribe to a running sim and receive updates with imperceptible lag
- A user can change a policy slider and see the effect within one or two ticks
- A scenario can be started, paused, reset, and branched cleanly
- The OpenAPI (or equivalent) spec is current and matches the actual code
- CI catches breaking changes before they hit `main`
- A teammate can deploy the project from scratch by following written steps in under 30 minutes

## Anti-patterns to avoid

- Designing the API around your implementation's convenience rather than the consumer's needs
- Skipping API versioning because "we'll never break it" (you will)
- Putting business logic in API handlers instead of in the sim layer
- Sending the entire world state on every WebSocket frame
- Letting CI rot — if it's red for more than a day, the team stops trusting it
- Building features that aren't wired into the daily smoke test
- Treating integration as someone else's problem

## Open questions you'll need to think through

- How does the sim communicate failure to the UI? (Crash? Slow tick? Stuck?)
- Should scenario runs be deterministic from the API's point of view — same request, same result?
- What's the right protocol for "user moved the policy slider while playback is paused"?
- How do you handle a long-running sim if the user closes their tab? Does it keep running server-side?
- For the demo: is the sim running on the demo machine, or on a remote server?

## Where to look first

- The main `PROJECT_SPEC.md` — sections 5, 8, 12, 17
- FastAPI documentation — particularly the WebSocket and dependency injection sections
- The OpenAPI specification — your API should have one and it should be accurate
- Real-time dashboard projects on GitHub for inspiration on streaming architectures
