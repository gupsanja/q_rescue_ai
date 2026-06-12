from q_rescue.domain.models import Ambulance, Assignment, Incident, OptimizationResult


class GreedyAllocator:
    """Severity-first nearest-ambulance baseline for Member 4."""

    name = "classical-greedy"

    def solve(
        self, ambulances: list[Ambulance], incidents: list[Incident]
    ) -> OptimizationResult:
        available = {ambulance.id: ambulance for ambulance in ambulances}
        assignments: list[Assignment] = []

        for incident in sorted(incidents, key=lambda item: item.severity, reverse=True):
            if not available:
                break
            ambulance = min(
                available.values(),
                key=lambda item: item.location.distance_to(incident.location),
            )
            distance = ambulance.location.distance_to(incident.location)
            assignments.append(Assignment(ambulance.id, incident.id, distance))
            del available[ambulance.id]

        return OptimizationResult(
            assignments=assignments,
            objective_value=sum(item.distance for item in assignments),
            solver_name=self.name,
        )

