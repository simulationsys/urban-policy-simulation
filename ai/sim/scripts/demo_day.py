"""Toy end-to-end run: build a synthetic population, ask every agent what
mode they would pick today under (a) dry conditions and (b) heavy rain,
print the resulting mode-share.

This is a SUB-02-only smoke run — no real network, no tick loop. Real
integration with SUB-01 (engine) and SUB-03 (routing) will replace
`default_alternatives` with live numbers.

Usage:  python -m sim.scripts.demo_day --n 5000
"""

from __future__ import annotations

import argparse
from collections import Counter

import numpy as np

from sim.agents.alternatives import default_alternatives
from sim.agents.mode_choice import ModeChoiceModel
from sim.agents.modes import Mode
from sim.agents.population import build_population


def _mode_share(counts: Counter[Mode], n: int) -> dict[str, str]:
    return {m.value: f"{counts.get(m, 0) / n:.1%}" for m in Mode}


def run(n: int, seed: int) -> None:
    rng = np.random.default_rng(seed)
    agents = build_population(n, rng=rng)
    model = ModeChoiceModel(rng=rng)

    for label, rain in [("dry", 0.0), ("heavy rain", 1.0)]:
        counts: Counter[Mode] = Counter()
        for a in agents:
            # Random trip distance 2-15 km, deterministic per agent.
            dist = 2.0 + (a.id % 13)
            alts = default_alternatives(a, distance_km=dist, rain_intensity=rain)
            counts[model.choose(a, alts)] += 1
        print(f"\nMode share ({label}, n={n}):")
        for mode, pct in _mode_share(counts, n).items():
            print(f"  {mode:6s} {pct}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=5000)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    run(args.n, args.seed)


if __name__ == "__main__":
    main()
