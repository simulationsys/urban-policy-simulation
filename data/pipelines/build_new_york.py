"""Build a real Manhattan road graph and a synthetic 5,000-person population."""

from pathlib import Path

import numpy as np
import osmnx as ox
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "processed_data"
CENTER = (40.7546, -73.9845)  # Midtown: Times Square, Bryant Park, Empire State Building
RADIUS_METERS = 2600
POPULATION = 5000


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ox.settings.cache_folder = str(ROOT / "simulation" / "cache")

    print(f"Downloading Manhattan roads within {RADIUS_METERS} m of Times Square...")
    graph = ox.graph_from_point(CENTER, dist=RADIUS_METERS, network_type="drive", simplify=True)
    graph = ox.truncate.largest_component(graph, strongly=True)
    ox.save_graphml(graph, filepath=OUT / "network.graphml")

    nodes = np.asarray([str(node) for node in graph.nodes], dtype=object)
    if len(nodes) < 2:
        raise RuntimeError("OpenStreetMap returned too few Manhattan road intersections")

    rng = np.random.default_rng(42)
    occupations = np.array(["Corporate", "Service", "Student", "Labor", "Unemployed"])
    population = pd.DataFrame({
        "home_node": rng.choice(nodes, POPULATION),
        "work_node": rng.choice(nodes, POPULATION),
        "income_bracket_numeric": rng.choice([1, 2, 3, 4, 5], POPULATION, p=[.12, .2, .28, .25, .15]),
        "age": rng.integers(18, 71, POPULATION),
        "has_car": rng.random(POPULATION) < .28,
        "has_bike": rng.random(POPULATION) < .18,
        "has_metro_pass": rng.random(POPULATION) < .65,
        "occupation": rng.choice(occupations, POPULATION, p=[.35, .3, .16, .12, .07]),
    })
    population.to_parquet(OUT / "synthetic_population.parquet", index=False)
    print(f"Saved {graph.number_of_nodes():,} intersections and {POPULATION:,} synthetic residents.")


if __name__ == "__main__":
    main()
