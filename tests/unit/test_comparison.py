import pytest

pytest.importorskip("qiskit_optimization")

from q_rescue.domain.models import Ambulance, Assignment, Incident, Location, Severity
from q_rescue.quantum.comparison import compare_solvers, sample_from_assignments
from q_rescue.quantum.qaoa_solver import QiskitQAOASolver
from q_rescue.quantum.qubo import AmbulanceAllocationQuboBuilder
from q_rescue.simulation.generator import DisasterScenario


def _small_scenario() -> DisasterScenario:
    return DisasterScenario(
        name="Comparison test",
        ambulances=[Ambulance("A1", Location(0, 0))],
        incidents=[
            Incident("I-low", Location(1, 0), Severity.LOW),
            Incident("I-critical", Location(2, 0), Severity.CRITICAL),
        ],
        hospitals=[],
    )


def test_assignments_are_encoded_for_shared_qubo_evaluation() -> None:
    scenario = _small_scenario()
    model = AmbulanceAllocationQuboBuilder().build(
        scenario.ambulances,
        scenario.incidents,
    )
    assignments = [Assignment("A1", "I-critical", 2.0)]

    sample = sample_from_assignments(model, assignments)

    assert sample[("A1", "I-critical")] == 1
    assert sample[("A1", "I-low")] == 0


def test_unknown_assignment_is_rejected() -> None:
    scenario = _small_scenario()
    model = AmbulanceAllocationQuboBuilder().build(
        scenario.ambulances,
        scenario.incidents,
    )

    with pytest.raises(ValueError, match="not present"):
        sample_from_assignments(model, [Assignment("A9", "I9", 0.0)])


def test_comparison_uses_shared_energy_and_reports_gaps() -> None:
    report = compare_solvers(
        _small_scenario(),
        qaoa_solver=QiskitQAOASolver(shots=512, seed=7, maxiter=30),
    )

    assert report.binary_variables == 2
    assert report.exact.qubo_energy <= report.classical.qubo_energy
    assert report.exact.qubo_energy <= report.qaoa.qubo_energy
    assert report.classical_gap == pytest.approx(
        report.classical.qubo_energy - report.exact.qubo_energy
    )
    assert report.qaoa_gap == pytest.approx(report.qaoa.qubo_energy - report.exact.qubo_energy)
    assert report.exact.feasible
    assert report.qaoa.feasible
    assert report.exact.metrics["critical_coverage_percent"] == 100.0


def test_comparison_reports_operational_metrics_for_each_solver() -> None:
    report = compare_solvers(
        _small_scenario(),
        qaoa_solver=QiskitQAOASolver(shots=512, seed=7, maxiter=30),
    )

    for benchmark in (report.classical, report.exact, report.qaoa):
        assert benchmark.runtime_seconds >= 0.0
        assert benchmark.metrics["coverage_percent"] == 50.0
        assert len(benchmark.assignments) == 1
