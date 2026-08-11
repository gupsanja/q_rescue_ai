from __future__ import annotations

import math

import pandas as pd

# Sheffield areas with a risk adjustment offset relative to the forecast severity
SHEFFIELD_AREAS = [
    ("Sheffield City Centre", 0.8),
    ("Darnall", 0.6),
    ("Attercliffe", 0.5),
    ("Meadowhall", 0.3),
    ("Hillsborough", 0.1),
    ("Ecclesall Road", -0.3),
]

# Maps M5 XGBoost severity labels to the 0-10 display scale
_M5_SEVERITY_TO_SCORE: dict[str, float] = {
    "Low": 2.5,
    "Moderate": 5.0,
    "High": 7.5,
    "Severe": 10.0,
}


def simulation_severity_score(simulation: dict) -> float:
    # Convert the backend severity scale (1-4) to the displayed 0-10 scale
    severity = max(1.0, min(4.0, float(simulation["severity"])))
    return round(severity / 4 * 10, 1)


def _risk_label(score: float) -> str:
    # Map a numeric risk score to a human-readable risk level label
    if score >= 8:
        return "Critical"
    if score >= 6:
        return "High"
    if score >= 3:
        return "Medium"
    return "Low"


def predict_outcome(simulation: dict) -> dict:
    # Start from the severity score on the 0-10 scale
    base_severity = simulation_severity_score(simulation)
    affected_population = int(simulation["affected_population"])

    # Population pressure increases forecast severity up to a cap of 1.5
    population_pressure = min(1.5, affected_population / 200_000)

    # Resource pressure is driven by the gap between recommended and available
    ambulance_gap = max(0, simulation["recommended_ambulances"] - simulation["available_ambulances"])
    team_gap = max(0, simulation["recommended_rescue_teams"] - simulation["available_rescue_teams"])
    resource_pressure = min(1.5, (ambulance_gap + team_gap) / 20)

    # Forecast severity combines base, population, and resource pressures
    forecast_severity = min(10, round(base_severity + population_pressure + resource_pressure, 1))

    # Casualty estimate scales linearly with forecast severity
    casualty_rate = forecast_severity / 100
    estimated_casualties = round(affected_population * casualty_rate)

    # Demand is at least the recommended count, or scaled from casualties
    ambulance_demand = max(simulation["recommended_ambulances"], math.ceil(estimated_casualties / 50))
    rescue_team_demand = max(simulation["recommended_rescue_teams"], math.ceil(estimated_casualties / 80))
    food_unit_demand = max(simulation["recommended_food_units"], math.ceil(affected_population / 250))

    # Response time worsens when there are more unmet resource needs
    resource_shortage = (
        max(0, ambulance_demand - simulation["available_ambulances"])
        + max(0, rescue_team_demand - simulation["available_rescue_teams"])
    )
    response_time = max(5, round(simulation["response_time"] + resource_shortage * 0.2))

    # Build per-area risk scores — selected location gets an extra boost
    risk_rows = []
    selected_location = simulation["location"]
    known_areas = {name for name, _ in SHEFFIELD_AREAS}
    areas = list(SHEFFIELD_AREAS)

    # Insert the selected location at the top if it is not already in the list
    if selected_location not in known_areas:
        areas.insert(0, (selected_location, 1.0))

    for area, adjustment in areas:
        selected_adjustment = 0.8 if area == selected_location else 0
        risk_score = min(10, max(0, round(forecast_severity + adjustment + selected_adjustment, 1)))
        risk_rows.append({"Area": area, "Risk Score": risk_score, "Risk Level": _risk_label(risk_score)})

    # Sort areas from highest to lowest risk for display
    risk_areas = pd.DataFrame(risk_rows).sort_values("Risk Score", ascending=False, ignore_index=True)

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
    # Apply fixed efficiency multipliers to simulate a quantum-optimised allocation
    # These are heuristic estimates — replace with real QUBO/QAOA solver output
    return {
        "severity": prediction["severity"],
        "estimated_casualties": round(prediction["estimated_casualties"] * 0.9),   # 10% fewer casualties
        "response_time": max(5, round(prediction["response_time"] * 0.8)),          # 20% faster response
        "ambulances": max(1, math.ceil(prediction["ambulances"] * 0.9)),            # 10% fewer ambulances needed
        "rescue_teams": max(1, math.ceil(prediction["rescue_teams"] * 0.9)),        # 10% fewer teams needed
        "food_units": max(1, math.ceil(prediction["food_units"] * 0.95)),           # 5% fewer food units needed
    }


def predict_outcome_from_payload(payload: dict, simulation: dict) -> dict:
    # Extract the aggregate summary from the M5 dashboard payload
    aggregate = payload.get("aggregate", {})
    predictions = payload.get("predictions", [])

    # Map the dominant severity label to the 0-10 score scale
    dominant = aggregate.get("dominant_severity", "Moderate")
    forecast_severity = _M5_SEVERITY_TO_SCORE.get(dominant, 5.0)

    mean_demand = float(aggregate.get("mean_resource_demand", 0))
    affected_population = int(simulation.get("affected_population", 0))

    # Derive response metrics from the XGBoost aggregate output
    estimated_casualties = round(affected_population * forecast_severity / 100)
    ambulance_demand = max(simulation["recommended_ambulances"], math.ceil(mean_demand))
    rescue_team_demand = max(simulation["recommended_rescue_teams"], math.ceil(mean_demand * 0.6))
    food_unit_demand = max(simulation["recommended_food_units"], math.ceil(affected_population / 250))
    response_time = max(5, round(simulation["response_time"] * (forecast_severity / 10)))

    if predictions:
        # Build risk area rows from per-incident XGBoost predictions
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
        # No per-incident predictions — fall back to the heuristic
        return {**predict_outcome(simulation), "_source": "heuristic"}

    return {
        "severity": forecast_severity,
        "estimated_casualties": estimated_casualties,
        "response_time": response_time,
        "ambulances": ambulance_demand,
        "rescue_teams": rescue_team_demand,
        "food_units": food_unit_demand,
        "risk_areas": risk_areas,
        "_source": "xgboost",  # signals to the UI that real model output is shown
    }


def get_prediction(simulation: dict) -> dict:
    # Try to use the real M5 XGBoost payload stored in session state
    try:
        import streamlit as st  # noqa: PLC0415
        payload = st.session_state.get("ai_dashboard_payload")
    except Exception:
        payload = None

    # Use real model output if available, otherwise fall back to heuristic
    if payload and payload.get("predictions"):
        return predict_outcome_from_payload(payload, simulation)

    return {**predict_outcome(simulation), "_source": "heuristic"}
