from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from q_rescue.classical.allocator import GreedyAllocator
from q_rescue.domain.models import Assignment, OptimizationResult
from q_rescue.metrics.evaluator import calculate_metrics
from q_rescue.quantum.qaoa_solver import ExactQuboSolver, QiskitQAOASolver, QuboSolver
from q_rescue.quantum.qubo import AmbulanceAllocationQuboBuilder, QuboModel, Variable
from q_rescue.simulation.generator import DisasterScenario


@dataclass(frozen=True)
class SolverBenchmark:
    solver_name: str
    runtime_seconds: float
    qubo_energy: float
    assignments: list[Assignment]
    feasible: bool
    metrics: dict[str, float]


@dataclass(frozen=True)
class ComparisonReport:
    scenario_name: str
    binary_variables: int
    classical: SolverBenchmark
    exact: SolverBenchmark
    qaoa: SolverBenchmark
    classical_gap: float
    qaoa_gap: float
    classical_relative_gap_percent: float
    qaoa_relative_gap_percent: float


def compare_solvers(
    scenario: DisasterScenario,
    *,
    builder: AmbulanceAllocationQuboBuilder | None = None,
    qaoa_solver: QuboSolver | None = None,
) -> ComparisonReport:
    """Benchmark classical, exact-QUBO, and QAOA solvers on one scenario."""
    builder = builder or AmbulanceAllocationQuboBuilder()
    qaoa_solver = qaoa_solver or QiskitQAOASolver()
    model = builder.build(scenario.ambulances, scenario.incidents)

    classical = _benchmark_classical(scenario, model)
    exact = _benchmark_qubo_solver(scenario, model, ExactQuboSolver())
    qaoa = _benchmark_qubo_solver(scenario, model, qaoa_solver)

    classical_gap = classical.qubo_energy - exact.qubo_energy
    qaoa_gap = qaoa.qubo_energy - exact.qubo_energy
    denominator = max(abs(exact.qubo_energy), 1e-12)

    return ComparisonReport(
        scenario_name=scenario.name,
        binary_variables=len(model.variables),
        classical=classical,
        exact=exact,
        qaoa=qaoa,
        classical_gap=classical_gap,
        qaoa_gap=qaoa_gap,
        classical_relative_gap_percent=100.0 * classical_gap / denominator,
        qaoa_relative_gap_percent=100.0 * qaoa_gap / denominator,
    )


def sample_from_assignments(
    model: QuboModel,
    assignments: list[Assignment],
) -> dict[Variable, int]:
    """Encode assignments as a complete binary sample for shared QUBO evaluation."""
    sample = {variable: 0 for variable in model.variables}
    for assignment in assignments:
        variable = (assignment.ambulance_id, assignment.incident_id)
        if variable not in sample:
            raise ValueError(f"Assignment {variable!r} is not present in the QUBO")
        sample[variable] = 1
    return sample


def _benchmark_classical(
    scenario: DisasterScenario,
    model: QuboModel,
) -> SolverBenchmark:
    started = perf_counter()
    result = GreedyAllocator().solve(scenario.ambulances, scenario.incidents)
    runtime = perf_counter() - started
    sample = sample_from_assignments(model, result.assignments)
    return _build_benchmark(scenario, model, sample, result.solver_name, runtime)


def _benchmark_qubo_solver(
    scenario: DisasterScenario,
    model: QuboModel,
    solver: QuboSolver,
) -> SolverBenchmark:
    started = perf_counter()
    sample, _ = solver.solve(model)
    runtime = perf_counter() - started
    return _build_benchmark(scenario, model, sample, solver.name, runtime)


def _build_benchmark(
    scenario: DisasterScenario,
    model: QuboModel,
    sample: dict[Variable, int],
    solver_name: str,
    runtime_seconds: float,
) -> SolverBenchmark:
    ambulance_by_id = {ambulance.id: ambulance for ambulance in scenario.ambulances}
    incident_by_id = {incident.id: incident for incident in scenario.incidents}
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
    feasible = _is_feasible(assignments, scenario)
    result = OptimizationResult(
        assignments=assignments,
        objective_value=model.evaluate(sample),
        solver_name=solver_name,
        feasible=feasible,
    )
    return SolverBenchmark(
        solver_name=solver_name,
        runtime_seconds=runtime_seconds,
        qubo_energy=result.objective_value,
        assignments=assignments,
        feasible=feasible,
        metrics=calculate_metrics(result, scenario.incidents),
    )


def _is_feasible(assignments: list[Assignment], scenario: DisasterScenario) -> bool:
    target = min(len(scenario.ambulances), len(scenario.incidents))
    ambulance_ids = [assignment.ambulance_id for assignment in assignments]
    incident_ids = [assignment.incident_id for assignment in assignments]
    return (
        len(assignments) == target
        and len(ambulance_ids) == len(set(ambulance_ids))
        and len(incident_ids) == len(set(incident_ids))
    )
