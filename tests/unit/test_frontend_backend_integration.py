import sys
from types import ModuleType, SimpleNamespace

from frontend.backend_integration import refresh_ai_integration


def test_non_flood_keeps_heuristic_and_clears_stale_ai_state():
    session = {
        "ai_dashboard_payload": {"stale": True},
        "ai_qubo_patch": {"stale": True},
        "ai_predictions": [{"stale": True}],
        "ai_quantum_allocation": {"stale": True},
    }

    status = refresh_ai_integration({"disaster_type": "Industrial accident"}, session)

    assert status["source"] == "heuristic"
    assert "ai_dashboard_payload" not in session
    assert "ai_qubo_patch" not in session
    assert "ai_predictions" not in session
    assert "ai_quantum_allocation" not in session


def test_flood_populates_validated_session_outputs(monkeypatch):
    predictions = [{"incident_id": "I1"}]
    patch = {"scenario_id": "flood", "severity_overrides": {"I1": 75}}
    dashboard = {"scenario_id": "flood", "predictions": predictions}
    quantum_allocation = {"solvers": {"exact-enumeration": {"status": "ok", "assignments": []}}}

    models_module = ModuleType("q_rescue.domain.models")
    models_module.DisasterCategory = SimpleNamespace(FLOOD="flood")

    allocation_module = ModuleType("q_rescue.services.allocation_output")
    allocation_module.AllocationSettings = lambda **kwargs: kwargs

    def fake_allocation(*args, **kwargs):
        assert kwargs["ai_patch"] == patch
        return quantum_allocation

    allocation_module.build_allocation_output = fake_allocation

    pipeline_module = ModuleType("q_rescue.services.validated_ai_pipeline")

    def fake_pipeline(**kwargs):
        assert kwargs["output_dir"] is None
        return predictions, patch, dashboard

    pipeline_module.run_validated_ai_prediction_pipeline = fake_pipeline

    distance_module = ModuleType("q_rescue.simulation.distance_matrix")
    distance_module.build_distance_matrix = lambda scenario: object()
    distance_module.build_severity_mapping = lambda scenario: {}

    scenarios_module = ModuleType("q_rescue.simulation.scenarios")
    scenarios_module.generate_scenario_by_category = lambda *args, **kwargs: object()

    monkeypatch.setitem(sys.modules, "q_rescue.domain.models", models_module)
    monkeypatch.setitem(
        sys.modules,
        "q_rescue.services.allocation_output",
        allocation_module,
    )
    monkeypatch.setitem(
        sys.modules,
        "q_rescue.services.validated_ai_pipeline",
        pipeline_module,
    )
    monkeypatch.setitem(
        sys.modules,
        "q_rescue.simulation.distance_matrix",
        distance_module,
    )
    monkeypatch.setitem(
        sys.modules,
        "q_rescue.simulation.scenarios",
        scenarios_module,
    )

    session = {}
    status = refresh_ai_integration(
        {"disaster_type": "Flood", "available_ambulances": 4},
        session,
    )

    assert status["source"] == "xgboost"
    assert session["ai_predictions"] == predictions
    assert session["ai_qubo_patch"] == patch
    assert session["ai_dashboard_payload"] == dashboard
    assert session["ai_quantum_allocation"] == quantum_allocation
