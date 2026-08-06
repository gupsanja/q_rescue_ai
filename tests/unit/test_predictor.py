from q_rescue.ai.predictor import build_dashboard_payload, build_qubo_patch


def test_build_qubo_patch():
    # Setup
    predictions = [
        {"incident_id": "I1", "flood_severity_weight": 75, "resource_demand_normalised": 0.8},
        {"incident_id": "I2", "flood_severity_weight": 25, "resource_demand_normalised": 0.2},
    ]

    # Act
    patch = build_qubo_patch(predictions, "test_scenario", "test_version")

    # Assert
    assert patch["scenario_id"] == "test_scenario"
    assert patch["model_version"] == "test_version"
    assert patch["severity_overrides"] == {"I1": 75, "I2": 25}
    assert patch["demand_overrides"] == {"I1": 0.8, "I2": 0.2}


def test_build_dashboard_payload_with_dict():
    # Setup
    predictions = [
        {
            "incident_id": "I1",
            "flood_severity_label": "High",
            "flood_severity_weight": 75,
            "resource_demand_units": 5000,
            "confidence": 0.9,
            "class_probabilities": {"High": 0.9},
            "model_version": "v1",
        }
    ]
    scenario = {
        "scenario_id": "test_scenario",
        "incidents": [{"id": "I1", "lat": 53.0, "lon": -1.5}],
    }

    # Act
    payload = build_dashboard_payload(predictions, scenario)

    # Assert
    assert payload["scenario_id"] == "test_scenario"
    assert payload["model_version"] == "v1"
    assert len(payload["predictions"]) == 1

    pred = payload["predictions"][0]
    assert pred["incident_id"] == "I1"
    assert pred["lat"] == 53.0
    assert pred["lon"] == -1.5

    agg = payload["aggregate"]
    assert agg["dominant_severity"] == "High"
    assert agg["total_predicted_demand"] == 5000
    assert "I1" in agg["high_risk_incident_ids"]
