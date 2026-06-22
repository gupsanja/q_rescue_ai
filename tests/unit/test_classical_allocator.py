from q_rescue.classical.allocator import GreedyAllocator, OptimalAssignmentAllocator
from q_rescue.domain.models import Ambulance, Incident, Location, Severity
from q_rescue.simulation.distance_matrix import DistanceMatrix


def test_optimal_allocator_beats_greedy_local_choice() -> None:
    ambulances = [
        Ambulance("A1", Location(0.0, 0.0)),
        Ambulance("A2", Location(0.0, 0.0)),
    ]
    incidents = [
        Incident("I-critical", Location(0.0, 0.0), Severity.CRITICAL),
        Incident("I-high", Location(0.0, 0.0), Severity.HIGH),
    ]
    distance_matrix = DistanceMatrix(
        matrix={
            "A1": {"I-critical": 1.0, "I-high": 2.0},
            "A2": {"I-critical": 1.1, "I-high": 100.0},
        },
        ambulance_ids=["A1", "A2"],
        incident_ids=["I-critical", "I-high"],
    )
    severity_mapping = {"I-critical": 100, "I-high": 75}

    greedy = GreedyAllocator().solve(ambulances, incidents, distance_matrix, severity_mapping)
    optimal = OptimalAssignmentAllocator().solve(
        ambulances,
        incidents,
        distance_matrix,
        severity_mapping,
    )

    assert [(a.ambulance_id, a.incident_id) for a in greedy.assignments] == [
        ("A1", "I-critical"),
        ("A2", "I-high"),
    ]
    assert [(a.ambulance_id, a.incident_id) for a in optimal.assignments] == [
        ("A1", "I-high"),
        ("A2", "I-critical"),
    ]
    assert optimal.objective_value < sum(assignment.distance for assignment in greedy.assignments)


def test_optimal_allocator_returns_empty_result_for_empty_inputs() -> None:
    result = OptimalAssignmentAllocator().solve([], [], DistanceMatrix(), {})

    assert result.assignments == []
    assert result.objective_value == 0.0
    assert result.feasible
