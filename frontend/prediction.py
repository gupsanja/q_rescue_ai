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

    backend = simulation["backend_results"]

    affected_population = int(simulation["affected_population"])

    ambulance_gap = max(
        0,
        backend["recommended_ambulances"]
        - simulation["available_ambulances"],
    )

    rescue_gap = max(
        0,
        backend["recommended_rescue_teams"]
        - simulation["available_rescue_teams"],
    )

    food_gap = max(
        0,
        backend["recommended_food_units"]
        - simulation["available_food_units"],
    )

    resource_pressure = min(
        1.5,
        (ambulance_gap + rescue_gap + food_gap) / 50,
    )

    base_severity = simulation_severity_score(simulation)

    population_pressure = min(
        1.5,
        affected_population / 200_000,
    )

    forecast_severity = min(
        10,
        round(
            base_severity
            + population_pressure
            + resource_pressure,
            1,
        ),
    )

    return {
        "severity": forecast_severity,

        "estimated_casualties": int(
            backend["estimated_casualties"] * 0.9
        ),

        "response_time": max(
            5,
            backend["response_time"] - 2,
        ),

        "ambulances": max(
            1,
            backend["recommended_ambulances"] - ambulance_gap,
        ),

        "rescue_teams": max(
            1,
            backend["recommended_rescue_teams"] - rescue_gap,
        ),

        "food_units": max(
            1,
            backend["recommended_food_units"] - food_gap,
        ),

        # Keep existing risk view compatibility
        "risk_areas": pd.DataFrame(
            [
                {
                    "Area": area,
                    "Risk Score": max(
                        0,
                        min(
                            10,
                            round(
                                forecast_severity + modifier,
                                1
                            )
                        )
                    ),
                    "Risk Level": _risk_label(
                        max(
                            0,
                            min(
                                10,
                                round(
                                    forecast_severity + modifier,
                                    1
                                )
                            )
                        )
                    ),
                }
                for area, modifier in SHEFFIELD_AREAS
            ]
        ),
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
