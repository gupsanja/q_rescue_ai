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
    model = AmbulanceAllocationQuboBuilder(constraint_penalty=100).build(
        ambulances, incidents
    )

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

