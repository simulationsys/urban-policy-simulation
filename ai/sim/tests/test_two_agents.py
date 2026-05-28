from __future__ import annotations

import numpy as np

from sim.agents.alternatives import default_alternatives
from sim.agents.mode_choice import ModeChoiceModel
from sim.agents.modes import Mode
from sim.scripts.demo_two_agents import make_priya, make_rohan


def test_two_agents_make_different_choices() -> None:
    """Priya (low income, no car) and Rohan (high income, car) should diverge."""
    model = ModeChoiceModel(rng=np.random.default_rng(0))
    priya = make_priya()
    rohan = make_rohan()

    priya_dry = model.choose(priya, default_alternatives(priya, distance_km=8.0), stochastic=False)
    rohan_dry = model.choose(rohan, default_alternatives(rohan, distance_km=8.0), stochastic=False)

    # They should not converge on the same mode under same conditions.
    assert priya_dry != rohan_dry
    # Rohan owns a car and weights comfort — should pick car.
    assert rohan_dry == Mode.CAR
    # Priya has no car; whatever she picks, it can't be car.
    assert priya_dry != Mode.CAR


def test_both_agents_respond_to_rain_in_their_own_way() -> None:
    model = ModeChoiceModel(rng=np.random.default_rng(0))
    priya = make_priya()
    rohan = make_rohan()

    # Rohan in a car is insensitive to rain — stays on car.
    rohan_dry = model.choose(rohan, default_alternatives(rohan, distance_km=8.0, rain_intensity=0.0), stochastic=False)
    rohan_wet = model.choose(rohan, default_alternatives(rohan, distance_km=8.0, rain_intensity=1.0), stochastic=False)
    assert rohan_dry == rohan_wet == Mode.CAR

    # Priya on a bike should move off bike when it pours.
    priya.has_bike = True
    priya_wet = model.choose(priya, default_alternatives(priya, distance_km=8.0, rain_intensity=1.0), stochastic=False)
    assert priya_wet != Mode.BIKE
    assert priya_wet != Mode.WALK
