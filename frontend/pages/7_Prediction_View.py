import pandas as pd
import plotly.express as px
import streamlit as st
from auth import require_login
from prediction import predict_outcome, simulation_severity_score
from ui_theme import apply_global_style, page_header, render_table

st.set_page_config(
    page_title="AI Prediction View",
    page_icon=":material/query_stats:",
    layout="wide",
)
apply_global_style()
require_login()

page_header("AI", "AI Prediction View")

if "simulation_results" not in st.session_state:
    st.warning("Run a simulation before opening the prediction view.")
    st.page_link(
        "pages/1_Disaster_Input.py",
        label="Open disaster input",
        icon=":material/edit_note:",
    )
    st.stop()

simulation = st.session_state["simulation_results"]
prediction = predict_outcome(simulation)

st.warning(
    "This is a deterministic prototype forecast based on the submitted scenario "
    "and resource availability. It is not output from a trained AI or clinical model."
)

metric_columns = st.columns(4)
metric_columns[0].metric(
    "Forecast severity",
    f"{prediction['severity']}/10",
    delta=round(prediction["severity"] - simulation_severity_score(simulation), 1),
)
metric_columns[1].metric(
    "Estimated casualties",
    f"{prediction['estimated_casualties']:,}",
)
metric_columns[2].metric(
    "Estimated response",
    f"{prediction['response_time']} min",
)
metric_columns[3].metric(
    "Highest-risk area",
    prediction["risk_areas"].iloc[0]["Area"],
)

st.subheader("Predicted resource demand")
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
    color_discrete_sequence=["#f2f2f2", "#ef232a"],
    pattern_shape_sequence=["", "/"],
    text_auto=True,
    title="Available resources vs predicted demand",
)
resource_chart.update_layout(
    plot_bgcolor="#17141c",
    paper_bgcolor="#17141c",
    font_color="#ffffff",
    legend_title_text="",
    yaxis_title="Number of units",
)

resource_col, table_col = st.columns([1.3, 1])
with resource_col:
    st.plotly_chart(resource_chart, width="stretch")
with table_col:
    render_table(resource_demand)

st.subheader("Forecast risk areas")
risk_chart = px.bar(
    prediction["risk_areas"],
    x="Area",
    y="Risk Score",
    color="Risk Level",
    pattern_shape="Risk Level",
    text="Risk Score",
    title="Predicted risk by Sheffield area",
    category_orders={
        "Risk Level": ["Low", "Medium", "High", "Critical"],
    },
    color_discrete_map={
        "Low": "#2ca25f",
        "Medium": "#3182bd",
        "High": "#ff9f1c",
        "Critical": "#ef232a",
    },
)
risk_chart.update_layout(
    plot_bgcolor="#17141c",
    paper_bgcolor="#17141c",
    font_color="#ffffff",
    yaxis={
        "title": "Risk score (0–10)",
        "range": [0, 10.8],
        "dtick": 1,
    },
)

st.plotly_chart(risk_chart, width="stretch")
render_table(prediction["risk_areas"])
