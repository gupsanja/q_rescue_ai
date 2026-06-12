import random

def generate_incident(idx):

    return {
        "id": f"I{idx}",
        "lat": random.uniform(53.35, 53.42),
        "lon": random.uniform(-1.55, -1.40),
        "severity": random.choice(
            ["Low", "Medium", "High", "Critical"]
        )
    }