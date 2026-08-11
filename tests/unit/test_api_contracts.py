import pytest

from q_rescue.api.contracts import (
    ContractValidationError,
    validate_prediction_request,
    validate_prediction_response,
    validate_qubo_patch_contract,
)


def valid_request(tmp_path):
    features = {
        "rainfall_24h_mm": 100,
        "rainfall_72h_mm": 180,
        "river_level_m": 4,
        "river_level_change_rate": 0.4,
        "soil_saturation_pct": 80,
        "upstream_dam_release_m3s": 120,
        "temperature_c": 12,
        "wind_speed_kmh": 30,
        "elevation_m": 80,
        "distance_to_river_km": 0.4,
        "drainage_capacity_index": 0.3,
        "urbanization_pct": 70,
        "population_density_per_km2": 2000,
        "previous_flood_history": 1,
    }
    return {
        "scenario_id": "scenario-1",
        "model_dir": str(tmp_path),
        "observations": [
            {
                "observation_id": "obs-1",
                "incident_id": "I1",
                "scenario_id": "scenario-1",
                **features,
            }
        ],
    }


def test_prediction_request_accepts_canonical_features(tmp_path):
    request = validate_prediction_request(valid_request(tmp_path))
    assert request.scenario_id == "scenario-1"
    assert request.observations[0]["incident_id"] == "I1"


def test_prediction_request_rejects_missing_features(tmp_path):
    request = valid_request(tmp_path)
    del request["observations"][0]["rainfall_24h_mm"]

    with pytest.raises(ContractValidationError) as exc:
        validate_prediction_request(request)

    assert exc.value.code == "MISSING_FEATURES"


def test_prediction_request_rejects_duplicate_incidents(tmp_path):
    request = valid_request(tmp_path)
    request["observations"].append(dict(request["observations"][0]))

    with pytest.raises(ContractValidationError) as exc:
        validate_prediction_request(request)

    assert exc.value.code == "DUPLICATE_INCIDENT_ID"


def test_qubo_patch_must_match_scenario():
    with pytest.raises(ContractValidationError) as exc:
        validate_qubo_patch_contract(
            {
                "scenario_id": "other",
                "model_version": "xgb_severity_v1",
                "severity_overrides": {"I1": 75},
                "demand_overrides": {"I1": 0.7},
            },
            scenario_id="scenario-1",
            incident_ids=["I1"],
        )

    assert exc.value.code == "SCENARIO_ID_MISMATCH"


def test_prediction_response_requires_full_incident_coverage():
    prediction = {
        "prediction_id": "PRED_scenario-1_I1",
        "incident_id": "I1",
        "scenario_id": "scenario-1",
        "flood_severity_label": "High",
        "flood_severity_int": 2,
        "flood_severity_enum": "HIGH",
        "flood_severity_weight": 75,
        "resource_demand_units": 10.0,
        "resource_demand_normalised": 0.7,
        "class_probabilities": {
            "Low": 0.1,
            "Moderate": 0.1,
            "High": 0.7,
            "Severe": 0.1,
        },
        "model_version": "xgb_severity_v1",
        "confidence": 0.7,
    }
    with pytest.raises(ContractValidationError) as exc:
        validate_prediction_response(
            [prediction],
            scenario_id="scenario-1",
            incident_ids=["I1", "I2"],
        )
    assert exc.value.code == "PREDICTION_COVERAGE_MISMATCH"
