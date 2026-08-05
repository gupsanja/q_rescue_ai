# Phase 2 AI Prediction & Integration Layer Documentation

This document describes the implementation details, architecture, data structures, and usage of the Phase 2 AI prediction layer (M5) and its integration with disaster simulation (M2), QUBO optimization (M1), dashboard visualization (M3), and pipeline orchestration (M4).

---

## 1. Overview

The Phase 2 AI Integration layer connects machine learning inference with the quantum allocation pipeline. It processes hydrological and geographic features from simulated flood incidents using trained XGBoost models to predict:
1. **Flood Severity** (Multi-class classification: `Low`, `Moderate`, `High`, `Severe`).
2. **Resource Demand** (Regression: composite index of required emergency response resources).

The outputs are transformed into format-compliant patches and payloads for consumption by downstream quantum solvers and UI dashboards.

---

## 2. Architecture & Data Flow

```
┌────────────────────────┐
│  M2 Simulation Engine  │
│  (scenarios/exporters) │
└───────────┬────────────┘
            │ DisasterScenario + Hydro Features
            ▼
┌────────────────────────┐
│ M4 Integration Service │ (run_ai_prediction_pipeline)
└───────────┬────────────┘
            │ observations dicts
            ▼
┌────────────────────────┐
│ M5 XGBoost Predictor   │ (predict_scenario)
│ (q_rescue.ai)          │
└───────────┬────────────┘
            ├──► AIPredictions (ai_predictions.json)
            ├──► QuboAIPatch (qubo_ai_patch.json) ────────────► M1 QUBO Builder (apply_ai_patch)
            └──► DashboardPayload (dashboard_prediction_payload.json) ──► M3 Streamlit UI
```

---

## 3. Module Reference

### `q_rescue.ai.label_mapper`
Provides canonical mappings and label encoding.
- `SEVERITY_ORDER`: `["Low", "Moderate", "High", "Severe"]`
- `AI_LABEL_TO_INT`: `{"Low": 0, "Moderate": 1, "High": 2, "Severe": 3}`
- `AI_LABEL_TO_SEVERITY_ENUM`: Maps AI labels to `Severity` enum members (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
- `AI_LABEL_TO_WEIGHT`: Maps labels to absolute QUBO weights (`25`, `50`, `75`, `100`).
- `CanonicalSeverityEncoder`: Sklearn-compatible encoder preserving canonical integer order (preventing alphabetical sorting bugs where `High=0`).

### `q_rescue.ai.validation`
Validates schema compliance per Phase 2 rules.
- `EXPECTED_FEATURES`: 14 canonical hydrological and socio-geographic feature column names.
- `validate_flood_observation_columns(columns)`
- `validate_ai_prediction(pred)`
- `validate_qubo_patch(patch, incident_ids)`

### `q_rescue.ai.predictor`
Core inference functions.
- `predict_scenario(scenario_id, observations, model_dir)`: Loads trained `joblib` model artifacts and normalizes predictions against training-set min/max values.
- `build_qubo_patch(predictions, scenario_id)`: Constructs `severity_overrides` and `demand_overrides` for M1.
- `build_dashboard_payload(predictions, scenario)`: Assembles aggregated severity counts, dominant severity, and per-incident metrics for M3.

### `q_rescue.quantum.qubo`
- `AmbulanceAllocationQuboBuilder.apply_ai_patch(patch)`: Stores AI patch state on the builder, overrides severity weights, and applies predicted demand as a separate urgency bonus during `build()`.

### `q_rescue.services.ai_integration`
- `run_ai_prediction_pipeline(scenario, hydro_params, model_dir, output_dir)`: End-to-end function that extracts observations, executes inference, constructs patch/dashboard artifacts, attaches predictions to incidents, and serializes output files.

---

## 4. Output Schemas

### `AIPrediction` (§2.2)
```json
{
  "prediction_id": "PRED_flood_sheffield_001_I3",
  "incident_id": "I3",
  "scenario_id": "flood_sheffield_001",
  "flood_severity_label": "High",
  "flood_severity_int": 2,
  "flood_severity_enum": "HIGH",
  "flood_severity_weight": 75,
  "resource_demand_units": 8431.7,
  "resource_demand_normalised": 0.72,
  "class_probabilities": {
    "Low": 0.03, "Moderate": 0.11, "High": 0.71, "Severe": 0.15
  },
  "model_version": "xgb_severity_v1",
  "confidence": 0.71
}
```

### `QuboAIPatch` (§2.4)
```json
{
  "scenario_id": "flood_sheffield_001",
  "model_version": "xgb_severity_v1",
  "severity_overrides": { "I1": 25, "I2": 75, "I3": 75 },
  "demand_overrides": { "I1": 0.32, "I2": 0.71, "I3": 0.72 }
}
```

---

## 5. Usage Example

```python
from pathlib import Path
from q_rescue.simulation.scenarios import generate_flood_scenario
from q_rescue.services.ai_integration import run_ai_prediction_pipeline
from q_rescue.quantum.qubo import AmbulanceAllocationQuboBuilder

# 1. Generate M2 Flood Scenario
scenario = generate_flood_scenario(seed=42)

# 2. Run AI Prediction Pipeline
model_dir = Path("flood_xgboost_project/outputs")
output_dir = Path("data/outputs/flood_sheffield_001")

predictions, qubo_patch, dashboard_payload = run_ai_prediction_pipeline(
    scenario=scenario,
    hydro_params={},
    model_dir=model_dir,
    output_dir=output_dir,
)

# 3. Apply Patch to QUBO Builder
builder = AmbulanceAllocationQuboBuilder(
    distance_weight=1.0,
    severity_weight=8.0,
    demand_weight=8.0,
)
patched_builder = builder.apply_ai_patch(qubo_patch)

# 4. Build Model with AI Overrides
# (distance_matrix and severity_mapping pre-computed via simulation)
qubo_model = patched_builder.build(
    scenario.ambulances,
    scenario.incidents,
    distance_matrix,
    severity_mapping,
)
```
