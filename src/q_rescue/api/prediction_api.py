"""AI Prediction Layer API adapter.

This is the single application-facing boundary for AI inference. It owns
request validation, model invocation, output validation, and conversion to
the QUBO/dashboard contracts. The underlying XGBoost predictor remains
unchanged.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from q_rescue.ai.predictor import (
    build_dashboard_payload,
    build_qubo_patch,
    predict_scenario,
)
from q_rescue.api.contracts import (
    ContractValidationError,
    PredictionResponse,
    validate_dashboard_prediction_payload,
    validate_prediction_request,
    validate_prediction_response,
    validate_qubo_patch_contract,
)


class PredictionAPI:
    """Stable service boundary around the AI Prediction Layer."""

    def predict(self, request: dict[str, Any]) -> dict[str, Any]:
        contract = validate_prediction_request(request)
        predictions = predict_scenario(
            contract.scenario_id,
            contract.observations,
            Path(contract.model_dir),
        )
        incident_ids = [str(item["incident_id"]) for item in contract.observations]
        validate_prediction_response(
            predictions,
            scenario_id=contract.scenario_id,
            incident_ids=incident_ids,
        )

        patch = build_qubo_patch(predictions, contract.scenario_id)
        validate_qubo_patch_contract(
            patch,
            scenario_id=contract.scenario_id,
            incident_ids=incident_ids,
        )

        # The API receives a prediction-compatible scenario dict so this
        # adapter does not create a dependency from the AI package on domain UI.
        scenario_for_dashboard = {
            "scenario_id": contract.scenario_id,
            "incidents": [
                {
                    "id": str(item["incident_id"]),
                    "lat": float(item.get("lat", item.get("latitude", 0.0))),
                    "lon": float(item.get("lon", item.get("longitude", 0.0))),
                }
                for item in contract.observations
            ],
        }
        dashboard_payload = build_dashboard_payload(predictions, scenario_for_dashboard)
        validate_dashboard_prediction_payload(
            dashboard_payload,
            scenario_id=contract.scenario_id,
            incident_ids=incident_ids,
        )

        return PredictionResponse(
            scenario_id=contract.scenario_id,
            predictions=predictions,
            qubo_patch=patch,
            dashboard_payload=dashboard_payload,
            validation={
                "status": "ok",
                "contract_version": "1.0",
                "prediction_count": len(predictions),
                "incident_count": len(incident_ids),
            },
        ).to_dict()


def predict_via_api(request: dict[str, Any]) -> dict[str, Any]:
    """Functional API entry point for scripts, services and future HTTP adapters."""
    return PredictionAPI().predict(request)


__all__ = ["PredictionAPI", "predict_via_api", "ContractValidationError"]
