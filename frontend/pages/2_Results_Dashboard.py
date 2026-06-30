import pandas as pd
import streamlit as st

from auth import require_login
from ui_theme import apply_global_style, page_header, render_table


st.set_page_config(page_title="Results Dashboard", page_icon=":bar_chart:", layout="wide")
apply_global_style()
require_login()

page_header("RS", "Simulation Results")

if "simulation_results" not in st.session_state:
    st.warning("Run a simulation from Disaster Input first.")
    st.stop()

results = st.session_state["simulation_results"]

summary = pd.DataFrame(
    {
        "Metric": [
            "Disaster Type",
            "Location",
            "Severity",
            "Affected Population",
            "Estimated Casualties",
            "Response Time",
            "Resources Needed",
            "Optimisation Score",
        ],
        "Metric Value": [
            results["disaster_type"],
            results["location"],
            results["severity"],
            f'{results["affected_population"]:,}',
            f'{results["estimated_casualties"]:,}',
            f'{results["response_time"]} min',
            results["resources_needed"],
            f'{results["optimisation_score"]}%',
        ],
    }
)

resources = pd.DataFrame(
    {
        "Resource Metric": ["Ambulances", "Rescue Teams", "Food Units"],
        "Available Count": [
            results["available_ambulances"],
            results["available_rescue_teams"],
            results["available_food_units"],
        ],
        "Recommended Count": [
            results["recommended_ambulances"],
            results["recommended_rescue_teams"],
            results["recommended_food_units"],
        ],
    }
)

risk = pd.DataFrame(
    {
        "Risk Level": ["Low", "Medium", "High", "Critical"],
        "Risk Percentage (%)": [
            results["low_risk"],
            results["medium_risk"],
            results["high_risk"],
            results["critical_risk"],
        ],
    }
)

col1, col2 = st.columns(2)
with col1:
    st.subheader("Summary")
    render_table(summary)
with col2:
    st.subheader("Resources")
    render_table(resources)

st.subheader("Risk")
render_table(risk)
