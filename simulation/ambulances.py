import random

def generate_ambulance(idx):

    return {
        "id": f"A{idx}",
        "lat": random.uniform(53.35, 53.42),
        "lon": random.uniform(-1.55, -1.40),
        "status": "Available"
    }