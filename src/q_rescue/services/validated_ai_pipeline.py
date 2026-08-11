"""Validated five-module AI integration owned by Lokesh.

This module composes the existing team-owned schema, predictor, simulation
exporter, QUBO patch builder, and dashboard payload builder without changing
their implementations.
"""

from __future__ import annotations

import json
from pathlib import Path

from q_rescue.ai.validation import validate_ai_prediction, validate_qubo_patch
from q_rescue.services.ai_integration import run_ai_prediction_pipeline
from q_rescue.simulation.exporters import export_hydro_enriched_scenario
from q_rescue.simulation.generator import DisasterScenario


def _validate_dashboard_payload(payload: dict, incident_ids: list[str]) -> None:
    """Validate dashboard output against the existing shared schema."""
    required = {
        "scenario_id",
        "model_version",
        "generated_at_utc",
        "predictions",
        "aggregate",
    }
    missing = required.difference(payload)
    if missing:
        raise ValueError(f"Dashboard payload missing fields: {sorted(missing)}")

    valid_ids = set(incident_ids)
    payload_ids = [str(item.get("incident_id")) for item in payload["predictions"]]
    unknown = set(payload_ids).difference(valid_ids)
    if unknown:
        raise ValueError(f"Dashboard payload contains unknown incident IDs: {sorted(unknown)}")
    if len(payload_ids) != len(set(payload_ids)):
        raise ValueError("Dashboard payload contains duplicate incident IDs")

    for item in payload["predictions"]:
        confidence = float(item.get("confidence", -1.0))
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"Dashboard confidence must be in [0, 1], got {confidence}")


def run_validated_ai_prediction_pipeline(
    scenario: DisasterScenario,
    hydro_params: dict,
    model_dir: Path,
    output_dir: Path | None = None,
) -> tuple[list[dict], dict, dict]:
    """Run and validate the M2 → M5 → M1/M3 integration boundary.

    Artifacts are written only after every shared-schema check passes.
    """
    predictions, qubo_patch, dashboard_payload = run_ai_prediction_pipeline(
        scenario=scenario,
        hydro_params=hydro_params,
        model_dir=model_dir,
        output_dir=None,
    )

    incident_ids = [incident.id for incident in scenario.incidents]
    for prediction in predictions:
        validate_ai_prediction(prediction)
    validate_qubo_patch(qubo_patch, incident_ids)
    _validate_dashboard_payload(dashboard_payload, incident_ids)

    prediction_ids = [prediction["incident_id"] for prediction in predictions]
    if set(prediction_ids) != set(incident_ids):
        missing = set(incident_ids).difference(prediction_ids)
        extra = set(prediction_ids).difference(incident_ids)
        raise ValueError(
            "Prediction coverage does not match scenario incidents: "
            f"missing={sorted(missing)}, extra={sorted(extra)}"
        )

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        artifacts = {
            "ai_predictions.json": predictions,
            "qubo_ai_patch.json": qubo_patch,
            "dashboard_prediction_payload.json": dashboard_payload,
        }
        for filename, payload in artifacts.items():
            target = output_dir / filename
            temporary = target.with_suffix(target.suffix + ".tmp")
            with temporary.open("w", encoding="utf-8") as stream:
                json.dump(payload, stream, indent=2)
            temporary.replace(target)

        export_hydro_enriched_scenario(
            scenario,
            output_dir / "hydro_enriched_scenario.json",
            hydro_params,
        )

    return predictions, qubo_patch, dashboard_payload
