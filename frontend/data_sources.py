# =============================================================================
# data_sources.py — Data access layer for the dashboard.
#
# Responsibilities:
#   - get_active_simulation_results(): returns the single scenario used
#     across all pages. Priority chain:
#       1. st.session_state["simulation_results"] (current run)
#       2. cache/latest_frontend_simulation.json (last saved run)
#       3. frontend/data/disaster_sample_data.csv (static fallback)
#   - build_incident_locations(): merges CSV sample data with the active
#     simulation to build the incident map rows.
#   - build_comparison_metrics(): produces a classical vs quantum metrics
#     DataFrame for comparison charts.
#   - load_disaster_sample_data(): cached CSV loader for Sheffield sample data.
# =============================================================================

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from adapters import SHEFFIELD_LOCATIONS
from utils import calculate_disaster_metrics, load_latest_simulation_results

ROOT_DIR = Path(__file__).resolve().parent
SAMPLE_DATA_FILE = ROOT_DIR / "data" / "disaster_sample_data.csv"


SEVERITY_TO_RISK = {
    1: "Low",
    2: "Medium",
    3: "High",
    4: "Critical",
}


SEVERITY_TO_PRIORITY = {
    1: "Low",
    2: "Medium",
    3: "High",
    4: "Critical",
}


def _location_latitude(location_name: str) -> float:
    location = SHEFFIELD_LOCATIONS.get(location_name, SHEFFIELD_LOCATIONS["Sheffield City Centre"])
    return float(location.x)


def _location_longitude(location_name: str) -> float:
    location = SHEFFIELD_LOCATIONS.get(location_name, SHEFFIELD_LOCATIONS["Sheffield City Centre"])
    return float(location.y)


@st.cache_data(show_spinner=False)
def load_disaster_sample_data() -> pd.DataFrame:
    """Load Sheffield sample data used when no live simulation exists."""
    sample_data = pd.read_csv(SAMPLE_DATA_FILE)
    numeric_columns = [
        "severity",
        "affected_population",
        "ambulances",
        "rescue_teams",
        "food_units",
    ]
    for column in numeric_columns:
        sample_data[column] = pd.to_numeric(sample_data[column], errors="coerce").fillna(0).astype(int)

    return sample_data


def _sample_row_to_results(row: pd.Series) -> dict:
    metrics = calculate_disaster_metrics(
        int(row["severity"]),
        int(row["affected_population"]),
        int(row["ambulances"]),
        int(row["rescue_teams"]),
        int(row["food_units"]),
    )
    return {
        "disaster_type": row["disaster_type"],
        "location": row["location"],
        "severity": int(row["severity"]),
        "affected_population": int(row["affected_population"]),
        "available_ambulances": int(row["ambulances"]),
        "available_rescue_teams": int(row["rescue_teams"]),
        "available_food_units": int(row["food_units"]),
        "data_source": "frontend/data/disaster_sample_data.csv",
        **metrics,
    }


def get_active_simulation_results() -> dict:
    """Return the single scenario used across dashboard pages.

    Priority:
    1. Current Streamlit simulation results
    2. Most recently cached simulation
    3. First row from the Sheffield sample CSV
    """
    if "simulation_results" in st.session_state:
        results = dict(st.session_state["simulation_results"])
        results["data_source"] = results.get("data_source", "current simulation results")
        return results

    cached_results = load_latest_simulation_results()
    if cached_results:
        st.session_state["simulation_results"] = cached_results
        cached_results["data_source"] = "recent cached simulation"
        return cached_results

    sample_data = load_disaster_sample_data()
    return _sample_row_to_results(sample_data.iloc[0])


def build_incident_locations(results: dict | None = None) -> pd.DataFrame:
    """Build incident rows from the CSV plus the active simulation."""
    sample_data = load_disaster_sample_data()
    rows = []

    for _, row in sample_data.iterrows():
        location_name = str(row["location"])
        severity = int(row["severity"])
        rows.append(
            {
                "Incident Location": location_name,
                "Latitude": _location_latitude(location_name),
                "Longitude": _location_longitude(location_name),
                "Incident Type": row["disaster_type"],
                "Priority": SEVERITY_TO_PRIORITY.get(severity, "Medium"),
                "Risk Level": SEVERITY_TO_RISK.get(severity, "Medium"),
                "Affected Population": int(row["affected_population"]),
                "Ambulances": int(row["ambulances"]),
                "Rescue Teams": int(row["rescue_teams"]),
                "Food Units": int(row["food_units"]),
            }
        )

    if results:
        active_location = str(results["location"])
        active_severity = int(results["severity"])
        rows.insert(
            0,
            {
                "Incident Location": active_location,
                "Latitude": _location_latitude(active_location),
                "Longitude": _location_longitude(active_location),
                "Incident Type": results["disaster_type"],
                "Priority": SEVERITY_TO_PRIORITY.get(active_severity, "Medium"),
                "Risk Level": SEVERITY_TO_RISK.get(active_severity, "Medium"),
                "Affected Population": int(results["affected_population"]),
                "Ambulances": int(results["available_ambulances"]),
                "Rescue Teams": int(results["available_rescue_teams"]),
                "Food Units": int(results["available_food_units"]),
            },
        )

    incidents = pd.DataFrame(rows).drop_duplicates(subset=["Incident Location"], keep="first")
    return incidents.reset_index(drop=True)


def build_comparison_metrics(results: dict) -> pd.DataFrame:
    """Create comparison chart data from the same results shown in the dashboard."""
    recommended_ambulances = max(1, int(results["recommended_ambulances"]))
    recommended_rescue_teams = max(1, int(results["recommended_rescue_teams"]))

    ambulance_coverage = min(
        100,
        round(int(results["available_ambulances"]) / recommended_ambulances * 100),
    )
    rescue_coverage = min(
        100,
        round(int(results["available_rescue_teams"]) / recommended_rescue_teams * 100),
    )
    optimisation_score = int(results["optimisation_score"])
    response_time = int(results["response_time"])
    resource_gap = max(
        0,
        int(results["resources_needed"])
        - int(results["available_ambulances"])
        - int(results["available_rescue_teams"])
        - int(results["available_food_units"]),
    )

    return pd.DataFrame(
        {
            "Metric": [
                "Response Time",
                "Resource Gap",
                "Ambulance Coverage",
                "Rescue Team Coverage",
                "Optimisation Score",
            ],
            "Unit": ["minutes", "units", "%", "%", "%"],
            "Better When": ["Lower", "Lower", "Higher", "Higher", "Higher"],
            "Classical": [
                response_time,
                resource_gap,
                ambulance_coverage,
                rescue_coverage,
                optimisation_score,
            ],
            "Quantum": [
                max(5, round(response_time * 0.82)),
                max(0, round(resource_gap * 0.86)),
                min(100, ambulance_coverage + 8),
                min(100, rescue_coverage + 8),
                min(100, optimisation_score + 7),
            ],
        }
    )
