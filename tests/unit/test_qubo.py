from q_rescue.domain.models import Ambulance, Incident, Location, Severity
from q_rescue.quantum.qaoa_solver import ExactQuboSolver
from q_rescue.quantum.qubo import AmbulanceAllocationQuboBuilder


def test_qubo_contains_one_variable_per_candidate_assignment() -> None:
    ambulances = [Ambulance("A1", Location(0, 0)), Ambulance("A2", Location(1, 1))]
    incidents = [
        Incident("I1", Location(2, 2), Severity.CRITICAL),
        Incident("I2", Location(3, 3), Severity.LOW),
    ]

    model = AmbulanceAllocationQuboBuilder().build(ambulances, incidents)

    assert len(model.variables) == 4
    assert ("A1", "I1") in model.variables


def test_exclusion_penalty_discourages_duplicate_ambulance_use() -> None:
    ambulances = [Ambulance("A1", Location(0, 0))]
    incidents = [
        Incident("I1", Location(0, 1), Severity.CRITICAL),
        Incident("I2", Location(0, 2), Severity.CRITICAL),
    ]
    model = AmbulanceAllocationQuboBuilder(constraint_penalty=100).build(ambulances, incidents)

    single = model.evaluate({("A1", "I1"): 1, ("A1", "I2"): 0})
    duplicate = model.evaluate({("A1", "I1"): 1, ("A1", "I2"): 1})

    assert duplicate > single


def test_exact_solver_returns_a_feasible_low_cost_sample() -> None:
    ambulances = [Ambulance("A1", Location(0, 0))]
    incidents = [Incident("I1", Location(0, 1), Severity.CRITICAL)]
    model = AmbulanceAllocationQuboBuilder().build(ambulances, incidents)

    sample, value = ExactQuboSolver().solve(model)

    assert sample[("A1", "I1")] == 1
    assert value < 0
def test_solver_uses_all_available_ambulances_when_incidents_are_available() -> None:
    ambulances = [
        Ambulance("A1", Location(0, 0)),
        Ambulance("A2", Location(10, 0)),
    ]
    incidents = [
        Incident("I1", Location(1, 0), Severity.LOW),
        Incident("I2", Location(9, 0), Severity.LOW),
        Incident("I3", Location(100, 100), Severity.LOW),
    ]
    model = AmbulanceAllocationQuboBuilder().build(ambulances, incidents)

    sample, _ = ExactQuboSolver().solve(model)

    assert sum(sample.values()) == 2


def test_solver_prioritises_critical_incident_when_resources_are_scarce() -> None:
    ambulances = [Ambulance("A1", Location(0, 0))]
    incidents = [
        Incident("I-low", Location(1, 0), Severity.LOW),
        Incident("I-critical", Location(2, 0), Severity.CRITICAL),
    ]
    model = AmbulanceAllocationQuboBuilder(
        distance_weight=1,
        severity_weight=8,
    ).build(ambulances, incidents)

    sample, _ = ExactQuboSolver().solve(model)

    assert sample[("A1", "I-critical")] == 1
    assert sample[("A1", "I-low")] == 0
