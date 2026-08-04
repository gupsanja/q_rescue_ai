from frontend.prediction import (
    predict_outcome,
    quantum_optimised_outcome,
    simulation_severity_score,
)


def scenario() -> dict:
    return {
        "severity": 3,
        "affected_population": 25_000,
        "location": "Darnall",
        "available_ambulances": 10,
        "available_rescue_teams": 6,
        "available_food_units": 50,
        "recommended_ambulances": 15,
        "recommended_rescue_teams": 9,
        "recommended_food_units": 100,
        "response_time": 24,
        "estimated_casualties": 2_250,
    }


def test_severity_is_converted_to_common_scale() -> None:
    assert simulation_severity_score(scenario()) == 7.5


def test_prediction_contains_required_dashboard_outputs() -> None:
    prediction = predict_outcome(scenario())

    assert 0 <= prediction["severity"] <= 10
    assert prediction["estimated_casualties"] > 0
    assert prediction["ambulances"] >= scenario()["recommended_ambulances"]
    assert not prediction["risk_areas"].empty
    assert set(prediction["risk_areas"].columns) == {
        "Area",
        "Risk Score",
        "Risk Level",
    }


def test_quantum_heuristic_does_not_increase_resource_demand() -> None:
    prediction = predict_outcome(scenario())
    quantum = quantum_optimised_outcome(prediction)

    assert quantum["response_time"] <= prediction["response_time"]
    assert quantum["ambulances"] <= prediction["ambulances"]
    assert quantum["rescue_teams"] <= prediction["rescue_teams"]
    assert quantum["food_units"] <= prediction["food_units"]
