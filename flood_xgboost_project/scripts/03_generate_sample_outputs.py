"""
Build a sample scenario (5 incidents, mirroring the schema's worked
example `flood_sheffield_001` / I1-I5) and run it through predict_scenario
-> build_qubo_patch -> build_dashboard_payload, exactly as M4's
run_ai_prediction_pipeline() will in Phase 2.

Writes:
  data/outputs/flood_sheffield_001/ai_predictions.json
  data/outputs/flood_sheffield_001/qubo_ai_patch.json
  data/outputs/flood_sheffield_001/dashboard_prediction_payload.json

These are for M2/M3/M4 to sanity-check their consumers against before the
real simulation engine (M2) is wired in, and are validated against the
schema §6 rules before being written.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from q_rescue.ai.predictor import predict_scenario, build_qubo_patch, build_dashboard_payload  # noqa: E402
from q_rescue.ai.validation import validate_ai_prediction, validate_qubo_patch  # noqa: E402

MODEL_DIR = REPO_ROOT / "flood_xgboost_project" / "outputs"
OUT_DIR = REPO_ROOT / "data" / "outputs" / "flood_sheffield_001"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SCENARIO_ID = "flood_sheffield_001"

# Five sample incidents with plausible Sheffield-area coordinates and
# hand-picked hydro features spanning the severity spectrum (Low..Severe),
# in the exact FloodObservation shape M2 will produce (schema §2.1).
INCIDENTS = [
    {"id": "I1", "lat": 53.3811, "lon": -1.4701, "profile": "low"},
    {"id": "I2", "lat": 53.3925, "lon": -1.4770, "profile": "moderate"},
    {"id": "I3", "lat": 53.405199, "lon": -1.466096, "profile": "high"},
    {"id": "I4", "lat": 53.4162, "lon": -1.4550, "profile": "severe"},
    {"id": "I5", "lat": 53.3700, "lon": -1.4900, "profile": "moderate"},
]

PROFILES = {
    "low": dict(
        rainfall_24h_mm=12.0, rainfall_72h_mm=28.0, river_level_m=1.8,
        river_level_change_rate=0.02, soil_saturation_pct=35.0,
        upstream_dam_release_m3s=20.0, temperature_c=14.0, wind_speed_kmh=10.0,
        elevation_m=120.0, distance_to_river_km=2.4, drainage_capacity_index=0.82,
        urbanization_pct=40.0, population_density_per_km2=650.0, previous_flood_history=0,
    ),
    "moderate": dict(
        rainfall_24h_mm=38.0, rainfall_72h_mm=85.0, river_level_m=3.2,
        river_level_change_rate=0.18, soil_saturation_pct=58.0,
        upstream_dam_release_m3s=60.0, temperature_c=11.5, wind_speed_kmh=18.0,
        elevation_m=70.0, distance_to_river_km=1.1, drainage_capacity_index=0.55,
        urbanization_pct=60.0, population_density_per_km2=1400.0, previous_flood_history=0,
    ),
    "high": dict(
        rainfall_24h_mm=76.5, rainfall_72h_mm=193.2, river_level_m=5.73,
        river_level_change_rate=0.49, soil_saturation_pct=87.4,
        upstream_dam_release_m3s=158.6, temperature_c=9.2, wind_speed_kmh=34.1,
        elevation_m=42.0, distance_to_river_km=0.8, drainage_capacity_index=0.38,
        urbanization_pct=68.5, population_density_per_km2=1850.0, previous_flood_history=1,
    ),
    "severe": dict(
        rainfall_24h_mm=118.0, rainfall_72h_mm=260.0, river_level_m=7.9,
        river_level_change_rate=0.85, soil_saturation_pct=96.0,
        upstream_dam_release_m3s=240.0, temperature_c=8.0, wind_speed_kmh=52.0,
        elevation_m=18.0, distance_to_river_km=0.3, drainage_capacity_index=0.22,
        urbanization_pct=78.0, population_density_per_km2=2600.0, previous_flood_history=1,
    ),
}

observations = []
for inc in INCIDENTS:
    feats = dict(PROFILES[inc["profile"]])
    observations.append(
        {
            "observation_id": f"OBS_{SCENARIO_ID}_{inc['id']}",
            "incident_id": inc["id"],
            "scenario_id": SCENARIO_ID,
            "timestamp_utc": "2026-03-14T08:30:00Z",
            **feats,
        }
    )

predictions = predict_scenario(SCENARIO_ID, observations, MODEL_DIR)
for p in predictions:
    validate_ai_prediction(p)

qubo_patch = build_qubo_patch(predictions, SCENARIO_ID)
validate_qubo_patch(qubo_patch, [inc["id"] for inc in INCIDENTS])

scenario = {"scenario_id": SCENARIO_ID, "incidents": INCIDENTS}
dashboard_payload = build_dashboard_payload(predictions, scenario)

with open(OUT_DIR / "ai_predictions.json", "w") as f:
    json.dump(predictions, f, indent=2)
with open(OUT_DIR / "qubo_ai_patch.json", "w") as f:
    json.dump(qubo_patch, f, indent=2)
with open(OUT_DIR / "dashboard_prediction_payload.json", "w") as f:
    json.dump(dashboard_payload, f, indent=2)

print(f"Wrote sample outputs to {OUT_DIR}")
for p in predictions:
    print(
        f"  {p['incident_id']}: {p['flood_severity_label']:9s} "
        f"(weight={p['flood_severity_weight']:3d}, "
        f"demand={p['resource_demand_units']:8.1f} units, "
        f"norm={p['resource_demand_normalised']:.3f}, "
        f"conf={p['confidence']:.2f})"
    )
