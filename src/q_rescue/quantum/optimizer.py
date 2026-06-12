from q_rescue.domain.models import Ambulance, Assignment, Incident, OptimizationResult
from q_rescue.quantum.qaoa_solver import ExactQuboSolver, QuboSolver
from q_rescue.quantum.qubo import AmbulanceAllocationQuboBuilder


class QuantumAllocator:
    def __init__(
        self,
        builder: AmbulanceAllocationQuboBuilder | None = None,
        solver: QuboSolver | None = None,
    ) -> None:
        self.builder = builder or AmbulanceAllocationQuboBuilder()
        self.solver = solver or ExactQuboSolver()

    def solve(self, ambulances: list[Ambulance], incidents: list[Incident]) -> OptimizationResult:
        model = self.builder.build(ambulances, incidents)
        sample, objective_value = self.solver.solve(model)
        ambulance_by_id = {item.id: item for item in ambulances}
        incident_by_id = {item.id: item for item in incidents}
        assignments = [
            Assignment(
                ambulance_id=ambulance_id,
                incident_id=incident_id,
                distance=ambulance_by_id[ambulance_id].location.distance_to(
                    incident_by_id[incident_id].location
                ),
            )
            for (ambulance_id, incident_id), selected in sample.items()
            if selected
        ]
        return OptimizationResult(
            assignments=assignments,
            objective_value=objective_value,
            solver_name=self.solver.name,
            feasible=self._is_feasible(assignments),
            metadata={"binary_variables": len(model.variables)},
        )

    @staticmethod
    def _is_feasible(assignments: list[Assignment]) -> bool:
        ambulance_ids = [item.ambulance_id for item in assignments]
        incident_ids = [item.incident_id for item in assignments]
        return len(ambulance_ids) == len(set(ambulance_ids)) and len(incident_ids) == len(
            set(incident_ids)
        )
