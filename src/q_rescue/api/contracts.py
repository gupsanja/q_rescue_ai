"""Shared API/data contracts for the Q-Rescue application.

The contracts are deliberately dependency-free so simulation, AI, optimisation,
metrics and dashboard code can exchange JSON-compatible objects without
depending on Streamlit, Qiskit, XGBoost or a web framework.

Validation is fail-closed: malformed data raises ``ContractValidationError``
before it is passed to a downstream component.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Any

from q_rescue.ai.validation import (
    EXPECTED_FEATURES,
    validate_ai_prediction,
    validate_flood_observation_columns,
    validate_qubo_patch,
)

CONTRACT_VERSION = "1.0"
AI_PREDICTION_API_VERSION = "1.0"


class ContractValidationError(ValueError):
    """Raised when a shared API contract is invalid."""

    def __init__(self, message: str, *, code: str = "CONTRACT_INVALID") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PredictionRequest:
    """Canonical AI Prediction Layer input contract."""

    scenario_id: str
    observations: list[dict[str, Any]]
    model_dir: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "api_version": AI_PREDICTION_API_VERSION,
            "scenario_id": self.scenario_id,
            "observations": self.observations,
            "model_dir": self.model_dir,
        }


@dataclass(frozen=True)
class PredictionResponse:
    """Canonical AI Prediction Layer output contract."""

    scenario_id: str
    predictions: list[dict[str, Any]]
    qubo_patch: dict[str, Any]
    dashboard_payload: dict[str, Any]
    validation: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "api_version": AI_PREDICTION_API_VERSION,
            "scenario_id": self.scenario_id,
            "status": "ok",
            "predictions": self.predictions,
            "qubo_patch": self.qubo_patch,
            "dashboard_payload": self.dashboard_payload,
            "validation": self.validation,
        }


def validate_prediction_request(payload: dict[str, Any]) -> PredictionRequest:
    """Validate and normalise the AI prediction request."""
    if not isinstance(payload, dict):
        raise ContractValidationError("Prediction request must be a JSON object", code="INVALID_TYPE")

    scenario_id = str(payload.get("scenario_id", "")).strip()
    if not scenario_id:
        raise ContractValidationError("scenario_id is required", code="MISSING_SCENARIO_ID")

    observations = payload.get("observations")
    if not isinstance(observations, list):
        raise ContractValidationError("observations must be a list", code="INVALID_OBSERVATIONS")

    model_dir = str(payload.get("model_dir", "")).strip()
    if not model_dir:
        raise ContractValidationError("model_dir is required", code="MISSING_MODEL_DIR")
    if not Path(model_dir).exists():
        raise ContractValidationError(
            f"model_dir does not exist: {model_dir}",
            code="MODEL_DIR_NOT_FOUND",
        )

    seen_incidents: set[str] = set()
    for index, observation in enumerate(observations):
        if not isinstance(observation, dict):
            raise ContractValidationError(
                f"observations[{index}] must be an object",
                code="INVALID_OBSERVATION",
            )
        try:
            validate_flood_observation_columns(EXPECTED_FEATURES)
        except AssertionError as exc:  # pragma: no cover - protects future schema edits
            raise ContractValidationError(str(exc), code="FEATURE_SCHEMA_INVALID") from exc

        missing = [feature for feature in EXPECTED_FEATURES if feature not in observation]
        if missing:
            raise ContractValidationError(
                f"observations[{index}] is missing features: {missing}",
                code="MISSING_FEATURES",
            )

        incident_id = str(observation.get("incident_id", "")).strip()
        if not incident_id:
            raise ContractValidationError(
                f"observations[{index}].incident_id is required",
                code="MISSING_INCIDENT_ID",
            )
        if incident_id in seen_incidents:
            raise ContractValidationError(
                f"duplicate incident_id: {incident_id}",
                code="DUPLICATE_INCIDENT_ID",
            )
        seen_incidents.add(incident_id)

        observation_scenario = str(observation.get("scenario_id", scenario_id))
        if observation_scenario != scenario_id:
            raise ContractValidationError(
                f"observation {incident_id} has scenario_id {observation_scenario!r}, "
                f"expected {scenario_id!r}",
                code="SCENARIO_ID_MISMATCH",
            )

        for feature in EXPECTED_FEATURES:
            try:
                value = float(observation[feature])
            except (TypeError, ValueError) as exc:
                raise ContractValidationError(
                    f"observations[{index}].{feature} must be numeric",
                    code="INVALID_FEATURE_VALUE",
                ) from exc
            if not isfinite(value):
                raise ContractValidationError(
                    f"observations[{index}].{feature} must be finite",
                    code="INVALID_FEATURE_VALUE",
                )

    return PredictionRequest(scenario_id, observations, model_dir)


def validate_prediction_response(
    predictions: list[dict[str, Any]],
    *,
    scenario_id: str,
    incident_ids: list[str],
) -> None:
    """Validate model output before it crosses the AI boundary."""
    expected_ids = set(incident_ids)
    actual_ids: set[str] = set()

    for prediction in predictions:
        try:
            validate_ai_prediction(prediction)
        except (AssertionError, TypeError, ValueError) as exc:
            raise ContractValidationError(
                f"Invalid AI prediction for {prediction.get('incident_id')!r}: {exc}",
                code="INVALID_AI_PREDICTION",
            ) from exc

        if prediction.get("scenario_id") != scenario_id:
            raise ContractValidationError(
                f"AI prediction scenario mismatch: {prediction.get('scenario_id')!r}",
                code="SCENARIO_ID_MISMATCH",
            )
        incident_id = str(prediction.get("incident_id", ""))
        if incident_id not in expected_ids:
            raise ContractValidationError(
                f"AI prediction contains unknown incident_id {incident_id!r}",
                code="UNKNOWN_INCIDENT_ID",
            )
        if incident_id in actual_ids:
            raise ContractValidationError(
                f"Duplicate AI prediction for {incident_id!r}",
                code="DUPLICATE_PREDICTION",
            )
        actual_ids.add(incident_id)

    if actual_ids != expected_ids:
        missing = sorted(expected_ids - actual_ids)
        raise ContractValidationError(
            f"AI prediction output does not cover all incidents; missing={missing}",
            code="PREDICTION_COVERAGE_MISMATCH",
        )


def validate_qubo_patch_contract(
    patch: dict[str, Any],
    *,
    scenario_id: str,
    incident_ids: list[str],
) -> None:
    """Validate the AI-to-QUBO hand-off."""
    if patch.get("scenario_id") != scenario_id:
        raise ContractValidationError(
            "QUBO patch scenario_id does not match prediction request",
            code="SCENARIO_ID_MISMATCH",
        )
    if not str(patch.get("model_version", "")).strip():
        raise ContractValidationError(
            "QUBO patch model_version is required",
            code="MISSING_MODEL_VERSION",
        )
    try:
        validate_qubo_patch(patch, incident_ids)
    except (AssertionError, TypeError, ValueError) as exc:
        raise ContractValidationError(
            f"Invalid QUBO patch: {exc}",
            code="INVALID_QUBO_PATCH",
        ) from exc


def validate_dashboard_prediction_payload(
    payload: dict[str, Any],
    *,
    scenario_id: str,
    incident_ids: list[str],
) -> None:
    """Validate the prediction payload consumed by dashboard code."""
    if payload.get("scenario_id") != scenario_id:
        raise ContractValidationError(
            "Dashboard payload scenario_id does not match prediction request",
            code="SCENARIO_ID_MISMATCH",
        )
    predictions = payload.get("predictions")
    aggregate = payload.get("aggregate")
    if not isinstance(predictions, list) or not isinstance(aggregate, dict):
        raise ContractValidationError(
            "Dashboard payload requires predictions[] and aggregate{}",
            code="INVALID_DASHBOARD_PAYLOAD",
        )

    ids = set()
    for item in predictions:
        if not isinstance(item, dict):
            raise ContractValidationError(
                "Dashboard prediction entries must be objects",
                code="INVALID_DASHBOARD_PREDICTION",
            )
        iid = str(item.get("incident_id", ""))
        if iid not in set(incident_ids):
            raise ContractValidationError(
                f"Dashboard payload contains unknown incident_id {iid!r}",
                code="UNKNOWN_INCIDENT_ID",
            )
        ids.add(iid)
        for key in ("lat", "lon", "resource_demand_units", "confidence"):
            if key not in item:
                raise ContractValidationError(
                    f"Dashboard prediction is missing {key!r}",
                    code="INVALID_DASHBOARD_PREDICTION",
                )
    if ids != set(incident_ids):
        raise ContractValidationError(
            "Dashboard payload does not cover every incident",
            code="PREDICTION_COVERAGE_MISMATCH",
        )
    for key in (
        "mean_resource_demand",
        "dominant_severity",
        "high_risk_incident_ids",
        "total_predicted_demand",
    ):
        if key not in aggregate:
            raise ContractValidationError(
                f"Dashboard aggregate is missing {key!r}",
                code="INVALID_DASHBOARD_AGGREGATE",
            )


def prediction_api_contract() -> dict[str, Any]:
    """Return a machine-readable summary of the AI API contract."""
    return {
        "api_version": AI_PREDICTION_API_VERSION,
        "request": {
            "scenario_id": "string",
            "model_dir": "string path",
            "observations": {
                "type": "array",
                "required_features": list(EXPECTED_FEATURES),
                "required_metadata": ["incident_id", "scenario_id"],
            },
        },
        "response": {
            "predictions": "AIPrediction[]",
            "qubo_patch": "QuboAIPatch",
            "dashboard_payload": "DashboardPredictionPayload",
            "validation": {"status": "ok|error", "fail_closed": True},
        },
        "rules": {
            "severity_labels": ["Low", "Moderate", "High", "Severe"],
            "severity_weights": [25, 50, 75, 100],
            "demand_normalised_range": [0.0, 1.0],
            "confidence_range": [0.0, 1.0],
            "one_prediction_per_incident": True,
        },
    }
