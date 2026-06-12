import json
import os

def save_outputs(scenario, cost_matrix):
    os.makedirs("outputs", exist_ok=True)
    with open("outputs/scenario.json", "w") as f:
        json.dump(scenario, f, indent=4)
    with open("outputs/cost_matrix.json", "w") as f:
        json.dump(cost_matrix, f, indent=4)