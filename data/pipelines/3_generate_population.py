import os
import random
import pandas as pd
import osmnx as ox
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "processed_data"
GRAPHML_PATH = DATA_DIR / "network.graphml"
OUTPUT_PATH = DATA_DIR / "synthetic_population.parquet"

NUM_AGENTS = 5000

def main():
    # Load network
    print(f"Loading network from {GRAPHML_PATH}...")
    try:
        G = ox.load_graphml(GRAPHML_PATH)
    except FileNotFoundError:
        print(f"Error: {GRAPHML_PATH} not found. Please run 1_download_osm_network.py first.")
        return
        
    valid_nodes = list(G.nodes)
    print(f"Loaded {len(valid_nodes)} valid nodes.")
    
    if len(valid_nodes) < 2:
        print("Error: Network does not have enough nodes to assign distinct home and work locations.")
        return

    agents = []
    
    # Income brackets and probabilities
    income_brackets = [1, 2, 3, 4, 5]
    income_weights = [0.20, 0.40, 0.25, 0.10, 0.05]
    
    # Ownership probabilities based on income bracket (1 to 5)
    car_probs = {1: 0.05, 2: 0.15, 3: 0.35, 4: 0.60, 5: 0.85}
    bike_probs = {1: 0.50, 2: 0.60, 3: 0.40, 4: 0.20, 5: 0.10}

    print(f"Generating {NUM_AGENTS} synthetic agents...")
    for i in range(1, NUM_AGENTS + 1):
        agent_id = f"agent_{i:05d}"
        
        # Sample home and work nodes, ensuring they are different
        home_node = random.choice(valid_nodes)
        work_node = random.choice(valid_nodes)
        while work_node == home_node:
            work_node = random.choice(valid_nodes)
            
        income = random.choices(income_brackets, weights=income_weights, k=1)[0]
        
        has_car = random.random() < car_probs[income]
        has_bike = random.random() < bike_probs[income]
        
        # New attributes
        age = max(18, min(70, int(random.gauss(35, 12))))
        
        occupations = ["Corporate", "Service", "Student", "Labor", "Unemployed"]
        occupation_weights = [0.30, 0.25, 0.20, 0.15, 0.10]
        occupation = random.choices(occupations, weights=occupation_weights, k=1)[0]
        
        # Strongly correlate metro pass with Corporate/Student and higher income
        metro_prob = 0.1
        if occupation in ["Corporate", "Student"]:
            metro_prob += 0.5
        if income >= 4:
            metro_prob += 0.3
            
        has_metro_pass = random.random() < min(1.0, metro_prob)
        
        agents.append({
            'id': agent_id,
            'home_node': home_node,
            'work_node': work_node,
            'income_bracket': income,
            'has_car': has_car,
            'has_bike': has_bike,
            'age': age,
            'occupation': occupation,
            'has_metro_pass': has_metro_pass
        })

    df = pd.DataFrame(agents)
    
    # Ensure output directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"Saving to {OUTPUT_PATH}...")
    df.to_parquet(OUTPUT_PATH, engine="pyarrow", index=False)
    print("Generation complete.")

if __name__ == "__main__":
    main()
