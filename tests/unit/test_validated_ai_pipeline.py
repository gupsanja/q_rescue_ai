import pytest

from q_rescue.services.validated_ai_pipeline import _validate_dashboard_payload


def _payload(predictions: list[dict]) -> dict:
    return {
        "scenario_id": "flood_sheffield",
        "model_version": "xgb_severity_v1",
        "generated_at_utc": "2026-08-11T00:00:00Z",
        "predictions": predictions,
        "aggregate": {},
    }


def test_dashboard_contract_accepts_known_unique_incidents():
    payload = _payload(
        [
            {"incident_id": "I1", "confidence": 0.85},
            {"incident_id": "I2", "confidence": 0.40},
        ]
    )

    _validate_dashboard_payload(payload, ["I1", "I2"])


def test_dashboard_contract_rejects_missing_required_fields():
    with pytest.raises(ValueError, match="missing fields"):
        _validate_dashboard_payload({"predictions": []}, [])


def test_dashboard_contract_rejects_unknown_or_duplicate_incidents():
    with pytest.raises(ValueError, match="unknown incident IDs"):
        _validate_dashboard_payload(
            _payload([{"incident_id": "I3", "confidence": 0.5}]),
            ["I1"],
        )

    with pytest.raises(ValueError, match="duplicate incident IDs"):
        _validate_dashboard_payload(
            _payload(
                [
                    {"incident_id": "I1", "confidence": 0.5},
                    {"incident_id": "I1", "confidence": 0.6},
                ]
            ),
            ["I1"],
        )


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_dashboard_contract_rejects_invalid_confidence(confidence):
    with pytest.raises(ValueError, match="confidence must be"):
        _validate_dashboard_payload(
            _payload([{"incident_id": "I1", "confidence": confidence}]),
            ["I1"],
        )
