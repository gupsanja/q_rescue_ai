from q_rescue.domain.models import Ambulance, Incident, Location, Severity
from q_rescue.quantum.qubo import AmbulanceAllocationQuboBuilder
from q_rescue.simulation.distance_matrix import DistanceMatrix

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
    patch = {
        "severity_overrides": {"I1": 100},
        "demand_overrides": {}
    }
    patched_builder = base_builder.apply_ai_patch(patch)
    patched_model = patched_builder.build(ambulances, incidents, dm, sm)
    
    # Expected patched cost = (1.0 * 10.0) - (1.0 * (100 / 100)) = 10.0 - 1.0 = 9.0
    assert patched_model.objective_linear[("A1", "I1")] == 9.0

def test_apply_ai_patch_overrides_demand():
    ambulances, incidents, dm, sm = _mock_data()
    
    base_builder = AmbulanceAllocationQuboBuilder(distance_weight=1.0, severity_weight=1.0)
    
    patch = {
        "severity_overrides": {"I1": 25},
        "demand_overrides": {"I1": 0.5}  # Halves the effective distance cost
    }
    patched_builder = base_builder.apply_ai_patch(patch)
    patched_model = patched_builder.build(ambulances, incidents, dm, sm)
    
    # Expected patched cost = (1.0 * 0.5 * 10.0) - (1.0 * (25 / 100)) = 5.0 - 0.25 = 4.75
    assert patched_model.objective_linear[("A1", "I1")] == 4.75
