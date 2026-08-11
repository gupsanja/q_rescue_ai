"""Safe frontend bridge to the validated backend AI pipeline."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import MutableMapping

_AI_SESSION_KEYS = (
    "ai_dashboard_payload",
    "ai_qubo_patch",
    "ai_predictions",
    "ai_quantum_allocation",
    "ai_integration_error",
)


def _clear_ai_state(session_state: MutableMapping[str, object]) -> None:
    for key in _AI_SESSION_KEYS:
        session_state.pop(key, None)


def refresh_ai_integration(
    simulation: dict,
    session_state: MutableMapping[str, object],
) -> dict:
    """Populate frontend session state from the validated flood AI pipeline.

    Non-flood scenarios and backend failures retain the existing heuristic
    frontend behaviour. The returned status is intended only for user feedback.
    """
    _clear_ai_state(session_state)

    if simulation.get("disaster_type") != "Flood":
        return {
            "source": "heuristic",
            "message": "AI model integration is currently available for Flood scenarios.",
        }

    repository_root = Path(__file__).resolve().parents[1]
    source_root = repository_root / "src"
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))

    try:
        from q_rescue.domain.models import DisasterCategory
        from q_rescue.services.allocation_output import (
            AllocationSettings,
            build_allocation_output,
        )
        from q_rescue.services.validated_ai_pipeline import (
            run_validated_ai_prediction_pipeline,
        )
        from q_rescue.simulation.distance_matrix import (
            build_distance_matrix,
            build_severity_mapping,
        )
        from q_rescue.simulation.scenarios import generate_scenario_by_category

        model_dir = repository_root / "flood_xgboost_project" / "outputs"
        scenario = generate_scenario_by_category(
            DisasterCategory.FLOOD,
            config={
                "simulation": {
                    "ambulances": min(
                        4,
                        max(1, int(simulation.get("available_ambulances", 3))),
                    ),
                    "incidents": 5,
                }
            },
        )
        predictions, qubo_patch, dashboard_payload = (
            run_validated_ai_prediction_pipeline(
                scenario=scenario,
                hydro_params={},
                model_dir=model_dir,
                output_dir=None,
            )
        )
        quantum_allocation = build_allocation_output(
            scenario,
            build_distance_matrix(scenario),
            build_severity_mapping(scenario),
            settings=AllocationSettings(run_exact=True, run_qaoa=False),
            request={"ai_patch": qubo_patch},
            source="validated_ai_frontend",
            ai_patch=qubo_patch,
        )
    except (AssertionError, ImportError, OSError, ValueError) as exc:
        session_state["ai_integration_error"] = str(exc)
        return {
            "source": "heuristic",
            "message": "Validated AI output was unavailable; existing heuristic output remains active.",
        }

    session_state["ai_predictions"] = predictions
    session_state["ai_qubo_patch"] = qubo_patch
    session_state["ai_dashboard_payload"] = dashboard_payload
    session_state["ai_quantum_allocation"] = quantum_allocation
    return {
        "source": "xgboost",
        "message": "Validated XGBoost predictions are ready for the dashboard and QUBO flow.",
    }
