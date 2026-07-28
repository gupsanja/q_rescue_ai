import pandas as pd
import plotly.express as px
import streamlit as st
from auth import require_login
from prediction import predict_outcome
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
backend = simulation["backend_results"]
classical = backend["classical_metrics"]
qaoa = backend["qaoa_metrics"]
prediction = predict_outcome(simulation)
classical_metrics = backend["classical_metrics"]
qaoa_metrics = backend["qaoa_metrics"]

st.warning(
    "AI-predicted values remain prototype heuristics. "
    "Classical Greedy and QAOA Optimised values are generated from the backend allocation pipeline."
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
        "Unit": [
            "0–10",
            "people",
            "minutes",
            "units",
            "units",
            "units",
        ],
        "Better When": [
            "Lower",
            "Lower",
            "Lower",
            "Context",
            "Context",
            "Context",
        ],

        "Classical Greedy": [
            simulation["severity"],
            simulation["backend_results"]["estimated_casualties"],
            classical_metrics["response_time"],
            classical_metrics["ambulances"],
            classical_metrics["rescue_teams"],
            classical_metrics["food_units"],
        ],

        "AI Predicted": [
            prediction["severity"],
            prediction["estimated_casualties"],
            prediction["response_time"],
            prediction["ambulances"],
            prediction["rescue_teams"],
            prediction["food_units"],
        ],

        "QAOA Optimised": [
            simulation["severity"],
            simulation["backend_results"]["estimated_casualties"],
            qaoa_metrics["response_time"],
            qaoa_metrics["ambulances"],
            qaoa_metrics["rescue_teams"],
            qaoa_metrics["food_units"],
        ],
    }
)

st.subheader("Three-way outcome table")
render_table(comparison)

resource_comparison = comparison[comparison["Unit"] == "units"]
resource_chart = px.bar(
    resource_comparison,
    x="Metric",
    y=[
        "Classical Greedy",
        "AI Predicted",
        "QAOA Optimised",
    ],
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
        "Outcome": [
            "Classical Greedy",
            "AI Predicted",
            "QAOA Optimised",
        ],
        "Response Time": [
            classical["response_time"],
            prediction["response_time"],
            qaoa["response_time"],
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