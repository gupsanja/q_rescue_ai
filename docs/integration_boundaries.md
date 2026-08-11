# Q-Rescue AI Integration Boundaries and API Contracts

## Purpose

This document defines the stable integration boundary between the simulation,
AI prediction, classical allocation, quantum allocation, metrics and dashboard
layers. Existing modules keep ownership of their algorithms; the shared service
layer owns orchestration and data contracts.

## Runtime boundary

```text
                    ┌──────────────────────┐
                    │   Simulation (M2)    │
                    │ DisasterScenario     │
                    └──────────┬───────────┘
                               │
                 distance + severity + hydro data
                               │
              ┌────────────────▼────────────────┐
              │ Shared Application Service (M4) │
              │ application_service.py          │
              └───────┬─────────────┬───────────┘
                      │             │
              ┌───────▼──────┐  ┌───▼──────────────┐
              │ AI Prediction │  │ Classical        │
              │ API (M5)      │  │ baseline (M4)    │
              └───────┬──────┘  └───┬──────────────┘
                      │              │
             QuboAIPatch              │ OptimizationResult
                      │              │
                ┌─────▼──────────────▼─────┐
                │ Quantum/QUBO allocation  │
                │ (M1)                     │
                └─────────────┬────────────┘
                              │
                       OptimizationResult
                              │
                     ┌────────▼────────┐
                     │ Metrics (M4)    │
                     └────────┬────────┘
                              │
                     ┌────────▼────────┐
                     │ Dashboard API   │
                     │ JSON payload    │
                     └─────────────────┘
```

## Ownership and boundaries

| Boundary | Producer | Consumer | Contract |
|---|---|---|---|
| Simulation → AI | Simulation | `PredictionAPI` | `PredictionRequest` |
| AI → QUBO | `PredictionAPI` | QUBO builder | `QuboAIPatch` |
| AI → Dashboard | `PredictionAPI` | dashboard | `DashboardPredictionPayload` |
| Simulation → classical | Simulation | classical allocator | `DisasterScenario`, `DistanceMatrix`, `SeverityMapping` |
| Simulation → quantum | Simulation | QUBO builder | same shared inputs |
| Solvers → metrics | Classical/quantum | metrics | `OptimizationResult` |
| All layers → dashboard | application service | Streamlit/API | unified dashboard payload |

The algorithms are not hidden behind the API. The API is an integration
boundary, not a replacement for the existing modules.

## Classical allocation baseline

Two classical references are exposed:

1. **`classical_baseline`** — `GreedyAllocator`: severity-first, nearest
   available ambulance. This is the simple interpretable baseline.
2. **`classical_optimal`** — `OptimalAssignmentAllocator`: min-cost-flow
   assignment using the same distance/severity inputs. This is the stronger
   classical benchmark used for comparison against the QUBO solution.

The baseline is always executed by `run_application_workflow()` before any
quantum result is considered.

## AI Prediction API

Implementation: `q_rescue.api.prediction_api.PredictionAPI`.

### Request

```json
{
  "api_version": "1.0",
  "scenario_id": "sheffield_flood_response_(seed=42)",
  "model_dir": "flood_xgboost_project/outputs",
  "observations": [
    {
      "observation_id": "OBS_scenario_I1",
      "incident_id": "I1",
      "scenario_id": "sheffield_flood_response_(seed=42)",
      "timestamp_utc": "2026-08-11T00:00:00Z",
      "lat": 53.40,
      "lon": -1.47,
      "rainfall_24h_mm": 100.0,
      "rainfall_72h_mm": 180.0,
      "river_level_m": 4.2,
      "river_level_change_rate": 0.4,
      "soil_saturation_pct": 80.0,
      "upstream_dam_release_m3s": 120.0,
      "temperature_c": 12.0,
      "wind_speed_kmh": 30.0,
      "elevation_m": 80.0,
      "distance_to_river_km": 0.4,
      "drainage_capacity_index": 0.3,
      "urbanization_pct": 70.0,
      "population_density_per_km2": 2000.0,
      "previous_flood_history": 1
    }
  ]
}
```

The fourteen model features are owned by `q_rescue.ai.validation.EXPECTED_FEATURES`.
No missing values, duplicate incident IDs, non-finite values or scenario ID
mismatches are accepted.

### Response

The response contains:

- `predictions[]`: severity, probability, confidence and resource demand.
- `qubo_patch`: AI severity and normalised demand overrides.
- `dashboard_payload`: map/table/aggregate prediction data.
- `validation`: contract version and coverage counts.

The response is rejected if a prediction is missing, contains an unknown
incident, has invalid probability/confidence ranges, or cannot be converted to
a valid QUBO patch.

## QUBO patch contract

```json
{
  "scenario_id": "sheffield_flood_response_(seed=42)",
  "model_version": "xgb_severity_v1",
  "severity_overrides": {"I1": 75},
  "demand_overrides": {"I1": 0.72}
}
```

- Severity weights: `25`, `50`, `75`, `100`.
- Demand: `[0.0, 1.0]`.
- Incident IDs must belong to the current scenario.
- The patch is applied only to the quantum builder.
- The patch never bypasses feasibility constraints.

## Dashboard contract

The application service returns one JSON-compatible object containing:

```text
contract_version
scenario
prediction
allocation
metrics
integration
```

This prevents the dashboard from rebuilding solver or AI logic itself.

## Validation behaviour

Validation is **fail-closed** at integration boundaries:

- malformed input → validation error;
- missing AI features → validation error;
- missing model artefacts → unavailable status;
- AI output mismatch → validation error;
- large QUBO → explicit skipped status rather than an unsafe exact run.

The system does not silently turn a failed AI prediction into a fabricated AI
result. Human-readable status and reason are exposed to the dashboard.

## Human decision boundary

The application produces recommendations, not autonomous emergency commands.
A qualified human operator remains responsible for dispatch, override and final
resource decisions.
