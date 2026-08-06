from q_rescue.domain.models import Ambulance, Incident, Location, Severity
from q_rescue.quantum.comparison import compare_solvers
from q_rescue.quantum.optimizer import QuantumAllocator
from q_rescue.quantum.qaoa_solver import ExactQuboSolver
from q_rescue.quantum.qubo import AmbulanceAllocationQuboBuilder
from q_rescue.simulation.distance_matrix import DistanceMatrix
from q_rescue.simulation.scenarios import generate_flood_scenario


def _mock_data():
    ambulances = [Ambulance("A1", Location(0, 0))]
    incidents = [Incident("I1", Location(1, 1), Severity.LOW)]
    dm = DistanceMatrix(
        matrix={"A1": {"I1": 10.0}},
        ambulance_ids=["A1"],
        incident_ids=["I1"],
    )
    sm = {"I1": 25}
    return ambulances, incidents, dm, sm


def test_apply_ai_patch_overrides_severity():
    ambulances, incidents, dm, sm = _mock_data()

    # 1. Base builder
    base_builder = AmbulanceAllocationQuboBuilder(distance_weight=1.0, severity_weight=1.0)
    base_model = base_builder.build(ambulances, incidents, dm, sm)

    # Expected cost = (1.0 * 10.0) - (1.0 * (25 / 100)) = 10.0 - 0.25 = 9.75
    assert base_model.objective_linear[("A1", "I1")] == 9.75

    # 2. Patched builder
    patch = {"severity_overrides": {"I1": 100}, "demand_overrides": {}}
    patched_builder = base_builder.apply_ai_patch(patch)
    patched_model = patched_builder.build(ambulances, incidents, dm, sm)

    # Expected patched cost = (1.0 * 10.0) - (1.0 * (100 / 100)) = 10.0 - 1.0 = 9.0
    assert patched_model.objective_linear[("A1", "I1")] == 9.0


def test_apply_ai_patch_adds_demand_priority_bonus():
    ambulances, incidents, dm, sm = _mock_data()

    base_builder = AmbulanceAllocationQuboBuilder(
        distance_weight=1.0,
        severity_weight=1.0,
        demand_weight=2.0,
    )

    patch = {
        "severity_overrides": {"I1": 25},
        "demand_overrides": {"I1": 0.5},
    }
    patched_builder = base_builder.apply_ai_patch(patch)
    patched_model = patched_builder.build(ambulances, incidents, dm, sm)

    # Expected patched cost = 10.0 - 0.25 - (2.0 * 0.5) = 8.75
    assert patched_model.objective_linear[("A1", "I1")] == 8.75


def test_high_predicted_demand_is_preferred_when_distance_and_severity_match():
    ambulances = [Ambulance("A1", Location(0, 0))]
    incidents = [
        Incident("I_LOW_DEMAND", Location(1, 1), Severity.HIGH),
        Incident("I_HIGH_DEMAND", Location(1, 1), Severity.HIGH),
    ]
    distance_matrix = DistanceMatrix(
        matrix={"A1": {"I_LOW_DEMAND": 10.0, "I_HIGH_DEMAND": 10.0}},
        ambulance_ids=["A1"],
        incident_ids=["I_LOW_DEMAND", "I_HIGH_DEMAND"],
    )
    severity_mapping = {"I_LOW_DEMAND": 75, "I_HIGH_DEMAND": 75}
    patch = {
        "severity_overrides": severity_mapping,
        "demand_overrides": {"I_LOW_DEMAND": 0.2, "I_HIGH_DEMAND": 0.9},
    }

    model = (
        AmbulanceAllocationQuboBuilder(
            distance_weight=1.0,
            severity_weight=8.0,
            demand_weight=8.0,
        )
        .apply_ai_patch(patch)
        .build(ambulances, incidents, distance_matrix, severity_mapping)
    )

    assert (
        model.objective_linear[("A1", "I_HIGH_DEMAND")]
        < model.objective_linear[("A1", "I_LOW_DEMAND")]
    )


def test_ai_patched_qubo_solves_to_feasible_priority_assignment():
    ambulances = [
        Ambulance("A1", Location(0, 0)),
        Ambulance("A2", Location(5, 0)),
    ]
    incidents = [
        Incident("I_NEAR_LOW", Location(1, 0), Severity.LOW),
        Incident("I_AI_URGENT", Location(4, 0), Severity.LOW),
        Incident("I_FAR_LOW", Location(20, 0), Severity.LOW),
    ]
    distance_matrix = DistanceMatrix(
        matrix={
            "A1": {"I_NEAR_LOW": 1.0, "I_AI_URGENT": 4.0, "I_FAR_LOW": 20.0},
            "A2": {"I_NEAR_LOW": 4.0, "I_AI_URGENT": 1.0, "I_FAR_LOW": 15.0},
        },
        ambulance_ids=["A1", "A2"],
        incident_ids=["I_NEAR_LOW", "I_AI_URGENT", "I_FAR_LOW"],
    )
    severity_mapping = {
        "I_NEAR_LOW": 25,
        "I_AI_URGENT": 25,
        "I_FAR_LOW": 25,
    }
    ai_patch = {
        "severity_overrides": {
            "I_NEAR_LOW": 25,
            "I_AI_URGENT": 100,
            "I_FAR_LOW": 25,
        },
        "demand_overrides": {
            "I_NEAR_LOW": 0.1,
            "I_AI_URGENT": 0.95,
            "I_FAR_LOW": 0.1,
        },
    }

    model = (
        AmbulanceAllocationQuboBuilder(
            distance_weight=1.0,
            severity_weight=8.0,
            demand_weight=8.0,
            critical_priority=True,
        )
        .apply_ai_patch(ai_patch)
        .build(ambulances, incidents, distance_matrix, severity_mapping)
    )

    sample, _ = ExactQuboSolver().solve(model)
    selected = [variable for variable, value in sample.items() if value]
    selected_ambulances = [ambulance_id for ambulance_id, _ in selected]
    selected_incidents = [incident_id for _, incident_id in selected]

    assert len(selected) == 2
    assert len(selected_ambulances) == len(set(selected_ambulances))
    assert len(selected_incidents) == len(set(selected_incidents))
    assert "I_AI_URGENT" in selected_incidents


def test_quantum_allocator_consumes_ai_patch_contract():
    ambulances = [
        Ambulance("A1", Location(0, 0)),
        Ambulance("A2", Location(6, 0)),
    ]
    incidents = [
        Incident("I_NEAR_LOW", Location(1, 0), Severity.LOW),
        Incident("I_AI_URGENT", Location(5, 0), Severity.LOW),
        Incident("I_FAR_LOW", Location(20, 0), Severity.LOW),
    ]
    distance_matrix = DistanceMatrix(
        matrix={
            "A1": {"I_NEAR_LOW": 1.0, "I_AI_URGENT": 5.0, "I_FAR_LOW": 20.0},
            "A2": {"I_NEAR_LOW": 5.0, "I_AI_URGENT": 1.0, "I_FAR_LOW": 14.0},
        },
        ambulance_ids=["A1", "A2"],
        incident_ids=["I_NEAR_LOW", "I_AI_URGENT", "I_FAR_LOW"],
    )
    severity_mapping = {
        "I_NEAR_LOW": 25,
        "I_AI_URGENT": 25,
        "I_FAR_LOW": 25,
    }
    qubo_patch = {
        "scenario_id": "member1_allocator_contract",
        "model_version": "mock_ai_contract_v1",
        "severity_overrides": {
            "I_NEAR_LOW": 25,
            "I_AI_URGENT": 100,
            "I_FAR_LOW": 25,
        },
        "demand_overrides": {
            "I_NEAR_LOW": 0.1,
            "I_AI_URGENT": 0.95,
            "I_FAR_LOW": 0.1,
        },
    }
    patched_builder = AmbulanceAllocationQuboBuilder(
        distance_weight=1.0,
        severity_weight=8.0,
        demand_weight=8.0,
        critical_priority=True,
    ).apply_ai_patch(qubo_patch)
    allocator = QuantumAllocator(builder=patched_builder, solver=ExactQuboSolver())

    result = allocator.solve(
        ambulances=ambulances,
        incidents=incidents,
        distance_matrix=distance_matrix,
        severity_mapping=severity_mapping,
    )

    assigned_incidents = {assignment.incident_id for assignment in result.assignments}

    assert result.feasible
    assert result.solver_name == "exact-enumeration"
    assert result.metadata["binary_variables"] == 6
    assert len(result.assignments) == 2
    assert "I_AI_URGENT" in assigned_incidents


def test_ai_patched_builder_runs_end_to_end_on_simulated_scenario():
    scenario = generate_flood_scenario(
        config={"simulation": {"ambulances": 2, "incidents": 3}},
        seed=42,
    )
    urgent_incident_id = scenario.incidents[-1].id
    ai_patch = {
        "scenario_id": "member1_ai_qubo_validation",
        "model_version": "mock_validation_v1",
        "severity_overrides": {
            incident.id: 100 if incident.id == urgent_incident_id else 25
            for incident in scenario.incidents
        },
        "demand_overrides": {
            incident.id: 0.95 if incident.id == urgent_incident_id else 0.05
            for incident in scenario.incidents
        },
    }
    builder = AmbulanceAllocationQuboBuilder(
        distance_weight=1.0,
        severity_weight=8.0,
        demand_weight=8.0,
        critical_priority=True,
    ).apply_ai_patch(ai_patch)

    report = compare_solvers(
        scenario,
        builder=builder,
        run_qaoa=False,
    )

    exact_assignments = report.exact.assignments
    assigned_ambulances = [assignment.ambulance_id for assignment in exact_assignments]
    assigned_incidents = [assignment.incident_id for assignment in exact_assignments]

    assert report.exact.feasible
    assert len(exact_assignments) == 2
    assert len(assigned_ambulances) == len(set(assigned_ambulances))
    assert len(assigned_incidents) == len(set(assigned_incidents))
    assert urgent_incident_id in assigned_incidents
