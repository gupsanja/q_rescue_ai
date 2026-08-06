"""XGBoost inference API — M5 deliverable (Phase 2, Week 2).

Implements the three public functions defined in schema §3.2:

    predict_scenario()      — batch inference → list[AIPrediction dicts]
    build_qubo_patch()      — predictions → QuboAIPatch dict (for M1)
    build_dashboard_payload() — predictions + scenario → DashboardPredictionPayload (for M3)

All outputs are validated against schema §6 rules before being returned.

Usage::

    from pathlib import Path
    from q_rescue.ai.predictor import predict_scenario, build_qubo_patch, build_dashboard_payload

    MODEL_DIR = Path("flood_xgboost_project/outputs")
    predictions = predict_scenario("flood_sheffield_001", observations, MODEL_DIR)
    patch = build_qubo_patch(predictions, "flood_sheffield_001")
    payload = build_dashboard_payload(predictions, scenario)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from q_rescue.ai.label_mapper import (
    AI_LABEL_TO_INT,
    AI_LABEL_TO_SEVERITY_ENUM,
    AI_LABEL_TO_WEIGHT,
    SEVERITY_ORDER,
    CanonicalSeverityEncoder,
)
from q_rescue.ai.validation import EXPECTED_FEATURES

# ---------------------------------------------------------------------------
# Internal model loader (cached per model_dir)
# ---------------------------------------------------------------------------

_MODEL_CACHE: dict[str, dict[str, Any]] = {}

_MODEL_VERSION = "xgb_severity_v1"


def _load_models(model_dir: Path) -> dict[str, Any]:
    """Load and cache the three model artefacts from *model_dir*.

    Args:
        model_dir: Directory containing ``xgb_severity_classifier.joblib``,
                   ``xgb_resource_regressor.joblib``, ``label_encoder.joblib``,
                   and ``normalization.json``.

    Returns:
        Dict with keys ``clf``, ``reg``, ``encoder``, ``norm_min``, ``norm_max``.
    """
    key = str(model_dir.resolve())
    if key not in _MODEL_CACHE:
        clf = joblib.load(model_dir / "xgb_severity_classifier.joblib")
        reg = joblib.load(model_dir / "xgb_resource_regressor.joblib")
        # label_encoder.joblib is a CanonicalSeverityEncoder instance
        encoder: CanonicalSeverityEncoder = joblib.load(model_dir / "label_encoder.joblib")

        norm_path = model_dir / "normalization.json"
        with norm_path.open() as f:
            norm = json.load(f)

        demand_norm = norm["resource_demand_units"]
        _MODEL_CACHE[key] = {
            "clf": clf,
            "reg": reg,
            "encoder": encoder,
            "norm_min": demand_norm["min"],
            "norm_max": demand_norm["max"],
        }
    return _MODEL_CACHE[key]


# ---------------------------------------------------------------------------
# Public API — schema §3.2
# ---------------------------------------------------------------------------


def predict_scenario(
    scenario_id: str,
    observations: list[dict],
    model_dir: Path,
) -> list[dict]:
    """Run XGBoost inference on all observations for a scenario.

    Each element of *observations* must be a ``FloodObservation`` dict
    (schema §2.1) containing at minimum the 14 feature fields defined in
    :data:`~q_rescue.ai.validation.EXPECTED_FEATURES`.  The metadata fields
    (``observation_id``, ``incident_id``, ``scenario_id``, ``timestamp_utc``)
    are also expected but are not used for inference — they are passed through
    to the output for traceability.

    Args:
        scenario_id:  The scenario identifier string (e.g. ``"flood_sheffield_001"``).
        observations: List of ``FloodObservation`` dicts produced by M2.
        model_dir:    Path to the directory containing trained model artefacts.

    Returns:
        A list of ``AIPrediction`` dicts (schema §2.2), one per observation,
        in the same order as *observations*.
    """
    if not observations:
        return []

    models = _load_models(Path(model_dir))
    clf = models["clf"]
    reg = models["reg"]
    encoder: CanonicalSeverityEncoder = models["encoder"]
    norm_min: float = models["norm_min"]
    norm_max: float = models["norm_max"]

    # Build feature DataFrame — use only the 14 canonical feature columns
    df = pd.DataFrame(observations)[EXPECTED_FEATURES].astype(float)

    # Batch inference
    clf_int_preds: np.ndarray = clf.predict(df)  # shape (n,)
    clf_proba: np.ndarray = clf.predict_proba(df)  # shape (n, 4)
    reg_preds: np.ndarray = reg.predict(df).astype(float)  # shape (n,)

    # Decode int predictions → label strings
    label_preds: list[str] = encoder.inverse_transform(clf_int_preds)

    predictions: list[dict] = []
    for idx, obs in enumerate(observations):
        label: str = label_preds[idx]
        sev_int: int = AI_LABEL_TO_INT[label]
        weight: int = AI_LABEL_TO_WEIGHT[label]
        sev_enum: str = AI_LABEL_TO_SEVERITY_ENUM[label]

        demand_raw: float = float(reg_preds[idx])
        # Normalise to [0, 1] using training-set statistics (schema §2.2)
        demand_norm_range = norm_max - norm_min
        if demand_norm_range > 0:
            demand_normalised = float(
                np.clip((demand_raw - norm_min) / demand_norm_range, 0.0, 1.0)
            )
        else:
            demand_normalised = 0.0

        # Class probabilities in canonical order (Low, Moderate, High, Severe)
        proba_row: np.ndarray = clf_proba[idx]
        class_probs: dict[str, float] = {
            SEVERITY_ORDER[i]: round(float(proba_row[i]), 6) for i in range(len(SEVERITY_ORDER))
        }
        # Normalise probabilities to exactly sum to 1.0 (floating-point safety)
        total_prob = sum(class_probs.values())
        if total_prob > 0:
            class_probs = {k: round(v / total_prob, 6) for k, v in class_probs.items()}

        confidence: float = round(float(proba_row[sev_int]), 4)

        incident_id: str = str(obs.get("incident_id", f"I{idx + 1}"))
        prediction_id: str = f"PRED_{scenario_id}_{incident_id}"

        predictions.append(
            {
                "prediction_id": prediction_id,
                "incident_id": incident_id,
                "scenario_id": scenario_id,
                "flood_severity_label": label,
                "flood_severity_int": sev_int,
                "flood_severity_enum": sev_enum,
                "flood_severity_weight": weight,
                "resource_demand_units": round(demand_raw, 2),
                "resource_demand_normalised": round(demand_normalised, 6),
                "class_probabilities": class_probs,
                "model_version": _MODEL_VERSION,
                "confidence": confidence,
            }
        )

    return predictions


def build_qubo_patch(
    predictions: list[dict],
    scenario_id: str,
    model_version: str = _MODEL_VERSION,
) -> dict:
    """Convert AI predictions into a QUBO severity/demand override dict.

    Produces a ``QuboAIPatch`` (schema §2.4) ready to be passed to
    :func:`~q_rescue.quantum.qubo.apply_ai_patch` by M1.

    Args:
        predictions:   List of ``AIPrediction`` dicts from :func:`predict_scenario`.
        scenario_id:   The scenario being optimised.
        model_version: Model version string for traceability.

    Returns:
        A ``QuboAIPatch`` dict with ``severity_overrides`` and ``demand_overrides``.
    """
    severity_overrides: dict[str, int] = {}
    demand_overrides: dict[str, float] = {}

    for pred in predictions:
        iid = pred["incident_id"]
        severity_overrides[iid] = pred["flood_severity_weight"]
        demand_overrides[iid] = round(float(pred["resource_demand_normalised"]), 6)

    return {
        "scenario_id": scenario_id,
        "model_version": model_version,
        "severity_overrides": severity_overrides,
        "demand_overrides": demand_overrides,
    }


def build_dashboard_payload(
    predictions: list[dict],
    scenario: Any,
) -> dict:
    """Assemble a dashboard-ready prediction payload for M3.

    Produces a ``DashboardPredictionPayload`` (schema §2.5).

    Args:
        predictions: List of ``AIPrediction`` dicts from :func:`predict_scenario`.
        scenario:    Either a ``DisasterScenario`` object (from M2/M4) or a plain
                     dict with keys ``scenario_id`` and ``incidents`` (where each
                     incident has ``id``, ``lat``, ``lon``).

    Returns:
        A ``DashboardPredictionPayload`` dict.
    """
    # Normalise the scenario argument to work with both DisasterScenario and dicts
    if hasattr(scenario, "name"):
        # DisasterScenario dataclass
        scenario_id: str = scenario.name.lower().replace(" ", "_")
        incident_coords: dict[str, tuple[float, float]] = {
            inc.id: (round(inc.location.x, 6), round(inc.location.y, 6))
            for inc in scenario.incidents
        }
    else:
        # Plain dict (used in sample output script and M4 pipeline)
        scenario_id = str(scenario.get("scenario_id", "unknown"))
        incidents_list = scenario.get("incidents", [])
        incident_coords = {
            str(inc.get("id", f"I{i}")): (
                float(inc.get("lat", 0.0)),
                float(inc.get("lon", 0.0)),
            )
            for i, inc in enumerate(incidents_list)
        }

    model_version = predictions[0]["model_version"] if predictions else _MODEL_VERSION
    generated_at = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    payload_predictions: list[dict] = []
    total_demand: float = 0.0
    severity_counts: dict[str, int] = {}

    for pred in predictions:
        iid = pred["incident_id"]
        lat, lon = incident_coords.get(iid, (0.0, 0.0))
        label = pred["flood_severity_label"]
        demand = float(pred["resource_demand_units"])
        total_demand += demand
        severity_counts[label] = severity_counts.get(label, 0) + 1

        payload_predictions.append(
            {
                "incident_id": iid,
                "lat": lat,
                "lon": lon,
                "flood_severity_label": label,
                "flood_severity_weight": pred["flood_severity_weight"],
                "resource_demand_units": round(demand, 2),
                "confidence": pred["confidence"],
                "class_probabilities": pred["class_probabilities"],
            }
        )

    # Dominant severity = label with the most predictions (tie-break: higher severity)
    dominant_severity: str = "Low"
    if severity_counts:
        dominant_severity = max(
            severity_counts,
            key=lambda lbl: (severity_counts[lbl], AI_LABEL_TO_INT[lbl]),
        )

    mean_demand = round(total_demand / len(predictions), 2) if predictions else 0.0
    high_risk_ids = [
        p["incident_id"] for p in predictions if p["flood_severity_label"] in ("High", "Severe")
    ]

    aggregate = {
        "mean_resource_demand": mean_demand,
        "dominant_severity": dominant_severity,
        "high_risk_incident_ids": high_risk_ids,
        "total_predicted_demand": round(total_demand, 2),
    }

    return {
        "scenario_id": scenario_id,
        "model_version": model_version,
        "generated_at_utc": generated_at,
        "predictions": payload_predictions,
        "aggregate": aggregate,
    }
