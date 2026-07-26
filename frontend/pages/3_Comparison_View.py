import pandas as pd
import plotly.express as px
import streamlit as st
from auth import require_login
from prediction import (
    predict_outcome,
    quantum_optimised_outcome,
    simulation_severity_score,
)
from ui_theme import apply_global_style, page_header, render_table

st.set_page_config(
    page_title="Comparison View",
    page_icon=":balance_scale:",
    layout="wide",
)
apply_global_style()
require_login()

page_header("QO", "Outcome Comparison")

if "simulation_results" not in st.session_state:
    st.warning("Run a simulation before opening the comparison view.")
    st.page_link(
        "pages/1_Disaster_Input.py",
        label="Open disaster input",
        icon=":material/edit_note:",
    )
    st.stop()

simulation = st.session_state["simulation_results"]
prediction = predict_outcome(simulation)
quantum = quantum_optimised_outcome(prediction)

st.warning(
    "AI-predicted and quantum-optimised values are transparent prototype "
    "heuristics. They are not outputs from a trained AI model or quantum solver."
)

comparison = pd.DataFrame(
    {
        "Metric": [
            "Severity score",
            "Estimated casualties",
            "Response time",
            "Ambulances",
            "Rescue teams",
            "Food units",
        ],
        "Unit": ["0–10", "people", "minutes", "units", "units", "units"],
        "Better When": ["Lower", "Lower", "Lower", "Context", "Context", "Context"],
        "Simulated": [
            simulation_severity_score(simulation),
            simulation["estimated_casualties"],
            simulation["response_time"],
            simulation["recommended_ambulances"],
            simulation["recommended_rescue_teams"],
            simulation["recommended_food_units"],
        ],
        "AI Predicted": [
            prediction["severity"],
            prediction["estimated_casualties"],
            prediction["response_time"],
            prediction["ambulances"],
            prediction["rescue_teams"],
            prediction["food_units"],
        ],
        "Quantum Optimised": [
            quantum["severity"],
            quantum["estimated_casualties"],
            quantum["response_time"],
            quantum["ambulances"],
            quantum["rescue_teams"],
            quantum["food_units"],
        ],
    }
)

st.subheader("Three-way outcome table")
render_table(comparison)

resource_comparison = comparison[comparison["Unit"] == "units"]
resource_chart = px.bar(
    resource_comparison,
    x="Metric",
    y=["Simulated", "AI Predicted", "Quantum Optimised"],
    barmode="group",
    title="Resource-demand comparison",
    color_discrete_sequence=["#f2f2f2", "#ef232a", "#7d5fff"],
    pattern_shape_sequence=["", "/", "x"],
    text_auto=True,
)
resource_chart.update_layout(
    plot_bgcolor="#17141c",
    paper_bgcolor="#17141c",
    font_color="#ffffff",
    legend_title_text="Outcome",
    yaxis_title="Number of units",
)

response_comparison = pd.DataFrame(
    {
        "Outcome": ["Simulated", "AI Predicted", "Quantum Optimised"],
        "Response Time": [
            simulation["response_time"],
            prediction["response_time"],
            quantum["response_time"],
        ],
    }
)
response_chart = px.bar(
    response_comparison,
    x="Outcome",
    y="Response Time",
    title="Response-time comparison",
    color="Outcome",
    pattern_shape="Outcome",
    color_discrete_sequence=["#f2f2f2", "#ef232a", "#7d5fff"],
    text="Response Time",
)
response_chart.update_layout(
    plot_bgcolor="#17141c",
    paper_bgcolor="#17141c",
    font_color="#ffffff",
    showlegend=False,
    yaxis_title="Response time (minutes)",
)
response_chart.update_traces(texttemplate="%{text} min", textposition="outside")

chart_col1, chart_col2 = st.columns(2)
with chart_col1:
    st.plotly_chart(resource_chart, width="stretch")
with chart_col2:
    st.plotly_chart(response_chart, width="stretch")

st.caption(
    "The prototype AI forecast uses scenario severity, population pressure, and "
    "resource gaps. The quantum-optimised estimate applies fixed efficiency "
    "assumptions to the forecast. Replace both with validated model/solver outputs "
    "when backend integrations are available."
)
