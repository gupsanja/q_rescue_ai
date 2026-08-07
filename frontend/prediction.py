"""Transparent prototype forecasts for the Q-Rescue prediction views.

The functions in this module are deterministic heuristics for an assignment
prototype. They are not outputs from a trained AI model or a quantum solver.
"""

from __future__ import annotations

import math

import pandas as pd

SHEFFIELD_AREAS = [
    ("Sheffield City Centre", 0.8),
    ("Darnall", 0.6),
    ("Attercliffe", 0.5),
    ("Meadowhall", 0.3),
    ("Hillsborough", 0.1),
    ("Ecclesall Road", -0.3),
]


def simulation_severity_score(simulation: dict) -> float:
    """Convert the backend severity scale (1–4) to the displayed 0–10 scale."""
    severity = max(1.0, min(4.0, float(simulation["severity"])))
    return round(severity / 4 * 10, 1)


def _risk_label(score: float) -> str:
    if score >= 8:
        return "Critical"
    if score >= 6:
        return "High"
    if score >= 3:
        return "Medium"
    return "Low"


def predict_outcome(simulation: dict) -> dict:
    """Estimate how the submitted scenario could develop."""
    base_severity = simulation_severity_score(simulation)
    affected_population = int(simulation["affected_population"])

    population_pressure = min(1.5, affected_population / 200_000)
    ambulance_gap = max(
        0,
        simulation["recommended_ambulances"] - simulation["available_ambulances"],
    )
    team_gap = max(
        0,
        simulation["recommended_rescue_teams"] - simulation["available_rescue_teams"],
    )
    resource_pressure = min(1.5, (ambulance_gap + team_gap) / 20)

    forecast_severity = min(
        10,
        round(base_severity + population_pressure + resource_pressure, 1),
    )
    casualty_rate = forecast_severity / 100
    estimated_casualties = round(affected_population * casualty_rate)

    ambulance_demand = max(
        simulation["recommended_ambulances"],
        math.ceil(estimated_casualties / 50),
    )
    rescue_team_demand = max(
        simulation["recommended_rescue_teams"],
        math.ceil(estimated_casualties / 80),
    )
    food_unit_demand = max(
        simulation["recommended_food_units"],
        math.ceil(affected_population / 250),
    )

    resource_shortage = max(
        0,
        ambulance_demand - simulation["available_ambulances"],
    ) + max(
        0,
        rescue_team_demand - simulation["available_rescue_teams"],
    )
    response_time = max(
        5,
        round(simulation["response_time"] + resource_shortage * 0.2),
    )

    risk_rows = []
    selected_location = simulation["location"]
    known_areas = {name for name, _ in SHEFFIELD_AREAS}
    areas = list(SHEFFIELD_AREAS)
    if selected_location not in known_areas:
        areas.insert(0, (selected_location, 1.0))

    for area, adjustment in areas:
        selected_adjustment = 0.8 if area == selected_location else 0
        risk_score = min(
            10,
            max(0, round(forecast_severity + adjustment + selected_adjustment, 1)),
        )
        risk_rows.append(
            {
                "Area": area,
                "Risk Score": risk_score,
                "Risk Level": _risk_label(risk_score),
            }
        )

    risk_areas = pd.DataFrame(risk_rows).sort_values(
        "Risk Score",
        ascending=False,
        ignore_index=True,
    )

    return {
        "severity": forecast_severity,
        "estimated_casualties": estimated_casualties,
        "response_time": response_time,
        "ambulances": ambulance_demand,
        "rescue_teams": rescue_team_demand,
        "food_units": food_unit_demand,
        "risk_areas": risk_areas,
    }


def quantum_optimised_outcome(prediction: dict) -> dict:
    """Estimate an outcome under a transparent efficient-allocation heuristic."""
    return {
        "severity": prediction["severity"],
        "estimated_casualties": round(prediction["estimated_casualties"] * 0.9),
        "response_time": max(5, round(prediction["response_time"] * 0.8)),
        "ambulances": max(1, math.ceil(prediction["ambulances"] * 0.9)),
        "rescue_teams": max(1, math.ceil(prediction["rescue_teams"] * 0.9)),
        "food_units": max(1, math.ceil(prediction["food_units"] * 0.95)),
    }


_M5_SEVERITY_TO_SCORE: dict[str, float] = {
    "Low": 2.5,
    "Moderate": 5.0,
    "High": 7.5,
    "Severe": 10.0,
}


def predict_outcome_from_payload(payload: dict, simulation: dict) -> dict:
    """Convert a real M5 DashboardPredictionPayload into the prediction dict shape.

    Replaces the heuristic when build_dashboard_payload() output is available
    in st.session_state['ai_dashboard_payload'].
    """
    aggregate = payload.get("aggregate", {})
    predictions = payload.get("predictions", [])

    dominant = aggregate.get("dominant_severity", "Moderate")
    forecast_severity = _M5_SEVERITY_TO_SCORE.get(dominant, 5.0)

    mean_demand = float(aggregate.get("mean_resource_demand", 0))
    affected_population = int(simulation.get("affected_population", 0))

    estimated_casualties = round(affected_population * forecast_severity / 100)
    ambulance_demand = max(simulation["recommended_ambulances"], math.ceil(mean_demand))
    rescue_team_demand = max(simulation["recommended_rescue_teams"], math.ceil(mean_demand * 0.6))
    food_unit_demand = max(simulation["recommended_food_units"], math.ceil(affected_population / 250))
    response_time = max(5, round(simulation["response_time"] * (forecast_severity / 10)))

    if predictions:
        risk_rows = [
            {
                "Area": p.get("incident_id", f"Incident {i + 1}"),
                "Risk Score": min(
                    10,
                    round(
                        _M5_SEVERITY_TO_SCORE.get(p.get("flood_severity_label", "Moderate"), 5.0)
                        * p.get("confidence", 1.0),
                        1,
                    ),
                ),
                "Risk Level": _risk_label(
                    _M5_SEVERITY_TO_SCORE.get(p.get("flood_severity_label", "Moderate"), 5.0)
                    * p.get("confidence", 1.0)
                ),
            }
            for i, p in enumerate(predictions)
        ]
        risk_areas = pd.DataFrame(risk_rows).sort_values("Risk Score", ascending=False, ignore_index=True)
    else:
        return {**predict_outcome(simulation), "_source": "heuristic"}

    return {
        "severity": forecast_severity,
        "estimated_casualties": estimated_casualties,
        "response_time": response_time,
        "ambulances": ambulance_demand,
        "rescue_teams": rescue_team_demand,
        "food_units": food_unit_demand,
        "risk_areas": risk_areas,
        "_source": "xgboost",
    }


def get_prediction(simulation: dict) -> dict:
    """Return the best available prediction for *simulation*.

    Uses the real M5 XGBoost payload from st.session_state['ai_dashboard_payload']
    when present; otherwise falls back to the deterministic heuristic.
    """
    try:
        import streamlit as st  # noqa: PLC0415
        payload = st.session_state.get("ai_dashboard_payload")
    except Exception:
        payload = None

    if payload and payload.get("predictions"):
        return predict_outcome_from_payload(payload, simulation)

    return {**predict_outcome(simulation), "_source": "heuristic"}
