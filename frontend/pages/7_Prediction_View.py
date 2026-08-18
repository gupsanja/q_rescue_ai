import pandas as pd
import plotly.express as px
import streamlit as st
from auth import require_login
from prediction import get_prediction, simulation_severity_score
from ui_theme import apply_global_style, page_header, render_table

st.set_page_config(page_title="AI Prediction View", page_icon=":material/query_stats:", layout="wide")
apply_global_style()
require_login()

page_header("AI", "AI Prediction View")

# Require a simulation to have been run before showing predictions
if "simulation_results" not in st.session_state:
    st.warning("Run a simulation before opening the prediction view.")
    st.page_link("pages/1_Disaster_Input.py", label="Open disaster input", icon=":material/edit_note:")
    st.stop()

simulation = st.session_state["simulation_results"]

# get_prediction checks for a real M5 XGBoost payload first, falls back to heuristic
prediction = get_prediction(simulation)

# Show a green banner for real model output, warning banner for the heuristic
if prediction.get("_source") == "xgboost":
    st.success("Showing live XGBoost model output from Member 5's pipeline.")

# Top-level metric cards — severity delta shows change from simulated baseline
metric_columns = st.columns(4)
metric_columns[0].metric(
    "Forecast severity",
    f"{prediction['severity']}/10",
    delta=round(prediction["severity"] - simulation_severity_score(simulation), 1),
)
metric_columns[1].metric("Estimated casualties", f"{prediction['estimated_casualties']:,}")
metric_columns[2].metric("Estimated response", f"{prediction['response_time']} min")
metric_columns[3].metric("Highest-risk area", prediction["risk_areas"].iloc[0]["Area"])

st.markdown("<h2 style='color:#212b32;font-weight:900;font-size:1.6rem;text-transform:uppercase;letter-spacing:0.04em;'>Predicted Resource Demand</h2>", unsafe_allow_html=True)

# Build a DataFrame comparing available resources against predicted demand
resource_demand = pd.DataFrame(
    {
        "Resource": ["Ambulances", "Rescue teams", "Food units"],
        "Available": [
            simulation["available_ambulances"],
            simulation["available_rescue_teams"],
            simulation["available_food_units"],
        ],
        "Predicted demand": [
            prediction["ambulances"],
            prediction["rescue_teams"],
            prediction["food_units"],
        ],
    }
)

resource_chart = px.bar(
    resource_demand,
    x="Resource",
    y=["Available", "Predicted demand"],
    barmode="group",
    color_discrete_sequence=["#005eb8", "#00a499"],
    text_auto=True,
    title="Available Resources vs Predicted Demand",
)
resource_chart.update_layout(
    plot_bgcolor="#ffffff",
    paper_bgcolor="#ffffff",
    font_color="#212b32",
    legend_title_text="",
    yaxis_title="Number of units",
    title_font={"size": 18, "color": "#212b32", "family": "Arial Black"},
    legend={"font": {"color": "#212b32", "size": 13}, "bgcolor": "rgba(0,0,0,0)"},
)

# Show the chart and the raw data table side by side
resource_col, table_col = st.columns([1.3, 1])
with resource_col:
    st.plotly_chart(resource_chart, width="stretch")
with table_col:
    render_table(resource_demand)

st.markdown("<h2 style='color:#212b32;font-weight:900;font-size:1.6rem;text-transform:uppercase;letter-spacing:0.04em;'>Forecast Risk Areas</h2>", unsafe_allow_html=True)

# Bar chart of predicted risk score per Sheffield area, colour-coded by level
risk_chart = px.bar(
    prediction["risk_areas"],
    x="Area",
    y="Risk Score",
    color="Risk Level",
    text="Risk Score",
    title="Predicted Risk by Sheffield Area",
    category_orders={"Risk Level": ["Low", "Medium", "High", "Critical"]},
    color_discrete_map={
        "Low": "#007f3b",
        "Medium": "#005eb8",
        "High": "#0072ce",
        "Critical": "#003087",
    },
)
risk_chart.update_layout(
    plot_bgcolor="#ffffff",
    paper_bgcolor="#ffffff",
    font_color="#212b32",
    yaxis={"title": "Risk score (0–10)", "range": [0, 10.8], "dtick": 1},
    title_font={"size": 18, "color": "#212b32", "family": "Arial Black"},
    legend={"font": {"color": "#212b32", "size": 13}, "bgcolor": "rgba(0,0,0,0)", "title_font": {"color": "#212b32"}},
)

st.plotly_chart(risk_chart, width="stretch")
