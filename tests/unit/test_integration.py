import pytest

from q_rescue.simulation.scenarios import generate_scenario_by_category
from q_rescue.domain.models import DisasterCategory
from q_rescue.simulation.cost_matrix import build_cost_matrix
from q_rescue.classical.allocator import GreedyAllocator
from q_rescue.quantum.qubo import AmbulanceAllocationQuboBuilder


def test_simulation_consumable_by_classical_allocator():
    scenario = generate_scenario_by_category(DisasterCategory.FLOOD)
    allocator = GreedyAllocator()

    # The classical allocator should be able to process the scenario
    # without raising exceptions.
    result = allocator.solve(scenario.ambulances, scenario.incidents)

    assert result.feasible is True
    # In a greedy allocation, every ambulance gets used if incidents >= ambulances
    assert len(result.assignments) == min(len(scenario.ambulances), len(scenario.incidents))


def test_simulation_consumable_by_qubo_builder():
    scenario = generate_scenario_by_category(DisasterCategory.INDUSTRIAL_ACCIDENT)
    builder = AmbulanceAllocationQuboBuilder()

    # The QUBO builder should be able to process the scenario directly
    model = builder.build(scenario.ambulances, scenario.incidents)

    # Check binary variable count (ambulances * incidents)
    expected_vars = len(scenario.ambulances) * len(scenario.incidents)
    assert len(model.variables) == expected_vars


def test_cost_matrix_aligns_with_qubo_builder():
    """Verify CostMatrix and QUBO linear terms agree when using the same distance function.

    The QUBO builder (Member 1) currently uses Euclidean distance_to() internally.
    To achieve an exact match, we pass that same distance function to build_cost_matrix().
    When Member 1 upgrades to Haversine, remove the distance_fn override here.
    """
    scenario = generate_scenario_by_category(DisasterCategory.GENERIC)

    # Member 1 uses Euclidean distance internally
    builder = AmbulanceAllocationQuboBuilder(distance_weight=1.0, severity_weight=8.0)
    qubo_model = builder.build(scenario.ambulances, scenario.incidents)

    # Use the same Euclidean distance_fn so both computations are identical
    euclidean_fn = lambda loc1, loc2: loc1.distance_to(loc2)  # noqa: E731
    cm = build_cost_matrix(
        scenario,
        distance_weight=1.0,
        severity_weight=8.0,
        distance_fn=euclidean_fn,
    )

    for a in scenario.ambulances:
        for i in scenario.incidents:
            qubo_cost = qubo_model.linear[(a.id, i.id)]
            matrix_cost = cm.matrix[a.id][i.id]
            assert pytest.approx(qubo_cost) == matrix_cost


def test_haversine_cost_matrix_differs_from_euclidean():
    """Document that the default Haversine cost matrix differs from QUBO Euclidean.

    This is expected behaviour — Haversine is the more accurate distance for
    real Sheffield lat/lon coordinates. When Member 1 updates the QUBO builder
    to use Location.haversine_to(), this test should be removed and the
    alignment test above should drop its distance_fn override.
    """
    scenario = generate_scenario_by_category(DisasterCategory.GENERIC)

    builder = AmbulanceAllocationQuboBuilder(distance_weight=1.0, severity_weight=8.0)
    qubo_model = builder.build(scenario.ambulances, scenario.incidents)

    # Default build_cost_matrix uses Haversine
    cm_haversine = build_cost_matrix(scenario, distance_weight=1.0, severity_weight=8.0)

    differences = []
    for a in scenario.ambulances:
        for i in scenario.incidents:
            qubo_cost = qubo_model.linear[(a.id, i.id)]
            haversine_cost = cm_haversine.matrix[a.id][i.id]
            if abs(qubo_cost - haversine_cost) > 1e-6:
                differences.append((a.id, i.id, qubo_cost, haversine_cost))

    # There should be differences between Euclidean and Haversine for lat/lon coords
    assert len(differences) > 0, (
        "Expected differences between Euclidean and Haversine costs for lat/lon coords"
    )
