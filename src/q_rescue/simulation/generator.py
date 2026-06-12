from dataclasses import dataclass
from random import Random

from q_rescue.domain.models import Ambulance, Incident, Location, Severity


@dataclass(frozen=True)
class DisasterScenario:
    name: str
    ambulances: list[Ambulance]
    incidents: list[Incident]


def generate_scenario(
    ambulance_count: int = 3,
    incident_count: int = 5,
    map_width_km: float = 20.0,
    seed: int = 42,
) -> DisasterScenario:
    """Create a deterministic synthetic scenario suitable for the Week 1 POC."""
    random = Random(seed)
    ambulances = [
        Ambulance(
            id=f"A{index + 1}",
            location=Location(random.uniform(0, map_width_km), random.uniform(0, map_width_km)),
        )
        for index in range(ambulance_count)
    ]
    incidents = [
        Incident(
            id=f"I{index + 1}",
            location=Location(random.uniform(0, map_width_km), random.uniform(0, map_width_km)),
            severity=Severity(random.randint(1, 4)),
        )
        for index in range(incident_count)
    ]
    return DisasterScenario("Synthetic flood response POC", ambulances, incidents)

