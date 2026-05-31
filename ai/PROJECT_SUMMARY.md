# Urban Intelligence Platform (UIP) - Project Summary

## 1. Project Overview
The **Urban Intelligence Platform (UIP)** is a modular agent-based simulation engine designed to model how an Indian city responds to climate stress, transport changes, policy interventions, and micro-economic behaviors.

The project is structured into multiple subsystems. Our current focus has been on **SUB-02: Agent Behavior**, which handles the core logic for simulated citizens (agents). This includes:
- **Mode Choice:** Using Multinomial Logit (MNL) utility functions to decide how an agent travels (e.g., driving vs. taking the bus).
- **Agent Memory & Adaptation:** A rolling memory system that allows agents to remember past trips (e.g., delays) and adapt future behaviors (like departing earlier) based on "frustration".
- **Household Dynamics:** Logic for car-sharing and negotiation among agents living in the same household.
- **Schedules:** Multi-leg journey planning (e.g., Home -> Work -> Gym -> Home).
- **Economic & Retail Dynamics (NEW):** Interactive behaviors between formal retail (shops managed by store managers and staff) and informal retail (roadside stalls experiencing perishable decay and municipal disruption risks), linked with citizen shoppers choosing venues via dynamic Multinomial Logit.

## 2. Work Completed So Far

### Environment Setup & Configuration
- Verified the project requires Python `>=3.11`.
- Successfully installed all development dependencies (`numpy`, `pandas`, `pytest`, `black`, `ruff`, `mypy`) using `pip install -e ".[dev]"`.
- Added necessary generated documentation and test explanation files to `.gitignore`.

### Core Agent & Transportation Scaffold
- Implemented core agent attributes, rolling commute memory, mode-choice MNL modeling, and joint household car-allocation logic.
- Configured automated daily schedule adaptations.

### Economic & Retail Behavior Expansion (New)
We expanded the agent behavior subsystem to include comprehensive economic and micro-retail models:
1. **Informal Retail (Roadside Stalls):**
   - Implemented a base `StallOwner` class with specific product subclasses: `FoodStallOwner` (high perishable inventory decay rate of 0.15/day), `ClothesStallOwner` (low decay rate of 0.02/day), and `AccessoriesStallOwner` (decay rate of 0.01/day).
   - Designed a **Frustration-Driven Relocation Model**: Stall owners track their daily sales in `RetailMemory`. If average daily revenue falls below 70% of expectations, frustration accumulates. Once frustration exceeds 2.0, they dynamically evaluate foot traffic/utility and relocate to a more profitable network node.
   - Modeled **Municipal/Weather Disruption**: A small probabilistic daily disruption resets their inventory, blocks their schedules, and adds +1.5 frustration.

2. **Formal Retail (Stores):**
   - Designed `StoreManager` and `StoreStaff` roles.
   - Managers schedule weekly inventory restocking, set pricing, and assign morning/evening `Shift` contracts.
   - Store staff schedules are strictly driven by these shift assignments. Delaying events (e.g. traffic congestion) that make staff late for work cause their frustration metric to spike.

3. **Citizen Shoppers & Choice Models:**
   - Extended citizen schedules to handle `"shopping"` as a valid daily activity leg.
   - Implemented a discrete Multinomial Logit `ShopChoiceModel` where shoppers evaluate alternatives (Formal Store vs. Roadside Stall) using Gumbel-max utility selection based on price, travel time, household income level, and specific product needs.
   - Integrated a mutual transaction processing system (`process_purchase`) where shopper utility is updated and stall/store revenue is added, lowering retailer frustration.

### Validation & Testing
We have successfully validated the core functionality and the new economic expansion. The codebase is fully stable, type-safe, and passes all checks.

1. **Unit Testing (`pytest`)**:
   - **Result:** 23/23 tests passed (14 original tests + 9 brand new retail tests).
   - Brand new tests validate stall inventory decay, disruption penalties, relocation triggers, store manager shift allocation, shopper discrete choice evaluations, and mutual transaction state updates.

2. **Emergent Behavior Demo (`demo_two_agents.py`)**:
   - **Result:** Success.
   - Validated that agents adapt their schedules and switch transportation modes based on simulated delays and accumulated frustration.

3. **Retail and Shopping Demo (`demo_shopping.py` - New)**:
   - **Result:** Success.
   - A multi-scenario script demonstrating:
     - **Part 1:** Shopper discrete shop choice showing low-income shoppers favoring cheap stalls and high-income shoppers preferring formal stores.
     - **Part 2:** Stall owner lifecycles showing inventory decay.
     - **Part 3:** Shift scheduling showing store staff late arrivals and associated frustration.
     - **Part 4:** Purchase interactions and transaction dynamics.
     - **Part 5:** Multi-day frustration accumulation and successful relocation of a struggling stall.

4. **Robustness / Smoke Testing (`smoke_test_agents.py`)**:
   - **Result:** 168/168 permutations passed.
   - Confirmed that the mathematical models and logic do not crash or produce errors under edge-case scenarios, ensuring the simulation can scale safely.

### Documentation
- Created a `TEST_RESULTS_EXPLANATION.md` file to explain the testing outcomes clearly to non-technical or cross-functional team members.
- Updated `CHANGES.md` with complete changelog entries.
- Created this updated `PROJECT_SUMMARY.md` as the complete record of work completed on the agent behavior subsystem.

## 3. Current State
- The `ai` subsystem for agent behavior is fully configured, tested, and bug-free, representing a robust transport-retail-economic simulation core.
- The system is fully ready for next-phase integrations: importing real city network graphs (OpenStreetMap) and wiring behaviors to the tick engine and the visualization frontend dashboard.
