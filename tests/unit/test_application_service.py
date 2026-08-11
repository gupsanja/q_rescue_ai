from pathlib import Path

from q_rescue.domain.models import DisasterCategory
from q_rescue.services.application_service import run_application_workflow
from q_rescue.simulation.scenarios import generate_scenario_by_category


def test_application_workflow_connects_simulation_classical_quantum_metrics_dashboard():
    scenario = generate_scenario_by_category(
        DisasterCategory.FLOOD,
        config={"simulation": {"ambulances": 2, "incidents": 3}},
        seed=42,
    )
    payload = run_application_workflow(
        scenario,
        model_dir=Path("flood_xgboost_project/outputs"),
        run_ai=True,
        run_quantum=True,
    )

    assert payload["contract_version"] == "1.0"
    assert payload["prediction"]["status"] == "ok"
    assert payload["prediction"]["qubo_patch"]["scenario_id"] == payload["scenario"]["id"]

    assert payload["allocation"]["classical_baseline"]["status"] == "ok"
    assert payload["allocation"]["classical_optimal"]["status"] == "ok"
    assert payload["allocation"]["quantum"]["status"] == "ok"
    assert payload["allocation"]["quantum"]["feasible"] is True

    assert "coverage_percent" in payload["metrics"]["classical_baseline"]
    assert payload["integration"]["ai_patch_applied_to_quantum"] is True
    assert payload["integration"]["human_oversight_required"] is True


def test_non_flood_workflow_has_explicit_ai_boundary():
    scenario = generate_scenario_by_category(
        DisasterCategory.GENERIC,
        config={"simulation": {"ambulances": 1, "incidents": 1}},
        seed=1,
    )
    payload = run_application_workflow(
        scenario,
        model_dir=Path("flood_xgboost_project/outputs"),
        run_ai=True,
        run_quantum=True,
    )

    assert payload["prediction"]["status"] == "not_applicable"
    assert payload["allocation"]["classical_baseline"]["status"] == "ok"
    assert payload["allocation"]["quantum"]["status"] == "ok"
