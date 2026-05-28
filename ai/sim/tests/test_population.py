from __future__ import annotations

from collections import Counter

import numpy as np

from sim.agents.alternatives import default_alternatives
from sim.agents.mode_choice import ModeChoiceModel
from sim.agents.modes import Mode
from sim.agents.population import build_population


def test_build_population_is_heterogeneous() -> None:
    rng = np.random.default_rng(0)
    agents = build_population(500, rng=rng)
    assert len(agents) == 500
    # Income bracket spans a real range.
    incomes = {a.income_bracket for a in agents}
    assert incomes.issubset({1, 2, 3, 4, 5})
    assert len(incomes) >= 3
    # Vehicle ownership varies.
    assert 0 < sum(a.has_car for a in agents) < 500
    assert 0 < sum(a.has_bike for a in agents) < 500
    # Per-agent weights are actually different.
    betas = {a.weights.beta_time for a in agents if a.weights}
    assert len(betas) > 100


def test_population_mode_share_shifts_with_rain() -> None:
    rng = np.random.default_rng(7)
    agents = build_population(1000, rng=rng)
    model = ModeChoiceModel(rng=rng)

    def share(rain: float) -> Counter[Mode]:
        c: Counter[Mode] = Counter()
        for a in agents:
            alts = default_alternatives(a, distance_km=8.0, rain_intensity=rain)
            c[model.choose(a, alts)] += 1
        return c

    dry = share(0.0)
    wet = share(1.0)
    # Sheltered modes should gain share under rain; exposed modes should lose.
    sheltered_gain = (wet[Mode.METRO] + wet[Mode.BUS]) - (dry[Mode.METRO] + dry[Mode.BUS])
    exposed_loss = (dry[Mode.BIKE] + dry[Mode.WALK]) - (wet[Mode.BIKE] + wet[Mode.WALK])
    assert sheltered_gain > 0
    assert exposed_loss > 0


def test_per_agent_weights_override_model_default() -> None:
    """An agent with extreme anti-cost weights should reject expensive modes."""
    from sim.agents.utility_weights import UtilityWeights

    rng = np.random.default_rng(0)
    agents = build_population(1, rng=rng)
    a = agents[0]
    a.has_car = True  # ensure car is available
    a.weights = UtilityWeights(beta_cost=-5.0)  # extreme cost aversion
    model = ModeChoiceModel(rng=np.random.default_rng(0))
    alts = default_alternatives(a, distance_km=8.0, rain_intensity=0.0)
    choice = model.choose(a, alts, stochastic=False)
    # Should not pick auto or car (most expensive).
    assert choice not in {Mode.AUTO, Mode.CAR}
