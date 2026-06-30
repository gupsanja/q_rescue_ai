import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from auth import require_login
from ui_theme import apply_global_style, page_header, render_table


st.set_page_config(page_title="Comparison View", page_icon=":balance_scale:", layout="wide")
apply_global_style()
require_login()

page_header("QO", "Optimisation Comparison")

comparison = pd.DataFrame(
    {
        "Metric": [
            "Response Time",
            "Fuel Usage",
            "Resource Utilisation",
            "Route Efficiency",
            "Allocation Accuracy",
        ],
        "Unit": ["minutes", "litres", "%", "%", "%"],
        "Better When": ["Lower", "Lower", "Higher", "Higher", "Higher"],
        "Classical": [18, 72, 78, 74, 80],
        "Quantum": [11, 58, 91, 89, 93],
    }
)

comparison_table = comparison.rename(
    columns={
        "Unit": "Metric Unit",
        "Classical": "Classical Metric Value",
        "Quantum": "Quantum Metric Value",
    }
)
render_table(comparison_table)

profile = comparison.copy()
profile[["Classical", "Quantum"]] = profile[["Classical", "Quantum"]].astype(float)
for metric in ["Response Time", "Fuel Usage"]:
    row = profile["Metric"] == metric
    best_value = profile.loc[row, ["Classical", "Quantum"]].min(axis=1)
    profile.loc[row, "Classical"] = (
        best_value / profile.loc[row, "Classical"] * 100
    )
    profile.loc[row, "Quantum"] = (
        best_value / profile.loc[row, "Quantum"] * 100
    )

for metric in ["Resource Utilisation", "Route Efficiency", "Allocation Accuracy"]:
    row = profile["Metric"] == metric
    best_value = profile.loc[row, ["Classical", "Quantum"]].max(axis=1)
    profile.loc[row, "Classical"] = (
        profile.loc[row, "Classical"] / best_value * 100
    )
    profile.loc[row, "Quantum"] = (
        profile.loc[row, "Quantum"] / best_value * 100
    )

radar_chart = go.Figure()
for method, color in [("Classical", "#ef232a"), ("Quantum", "#f2f2f2")]:
    radar_chart.add_trace(
        go.Scatterpolar(
            r=profile[method],
            theta=profile["Metric"],
            fill="toself",
            name=method,
            line=dict(color=color, width=3),
            fillcolor="rgba(239, 35, 42, 0.24)"
            if method == "Classical"
            else "rgba(242, 242, 242, 0.14)",
            hovertemplate=f"{method}<br>%{{theta}}: %{{r:.1f}}%<extra></extra>",
        )
    )

radar_chart.update_layout(
    title="Performance Profile (Higher Is Better)",
    paper_bgcolor="#221f27",
    plot_bgcolor="#221f27",
    font_color="#ffffff",
    polar=dict(
        bgcolor="#221f27",
        radialaxis=dict(
            visible=True,
            range=[0, 105],
            ticksuffix="%",
            gridcolor="rgba(255, 255, 255, 0.18)",
        ),
        angularaxis=dict(gridcolor="rgba(255, 255, 255, 0.18)"),
    ),
    legend=dict(orientation="h", yanchor="bottom", y=1.08, xanchor="center", x=0.5),
    margin=dict(l=60, r=60, t=100, b=50),
)

st.plotly_chart(radar_chart, use_container_width=True)

bar_chart = px.bar(
    comparison,
    x="Metric",
    y=["Classical", "Quantum"],
    barmode="group",
    title="Classical vs Quantum",
    color_discrete_sequence=["#ef232a", "#f2f2f2"],
)
bar_chart.update_layout(
    plot_bgcolor="#221f27",
    paper_bgcolor="#221f27",
    font_color="#ffffff",
)

totals = pd.DataFrame(
    {
        "Method": ["Classical", "Quantum"],
        "Score": [comparison["Classical"].sum(), comparison["Quantum"].sum()],
    }
)
pie_chart = px.pie(
    totals,
    names="Method",
    values="Score",
    title="Overall Performance",
    color_discrete_sequence=["#ef232a", "#f2f2f2"],
)
pie_chart.update_layout(
    paper_bgcolor="#221f27",
    font_color="#ffffff",
)

chart_col1, chart_col2 = st.columns(2)
with chart_col1:
    st.plotly_chart(bar_chart, use_container_width=True)
with chart_col2:
    st.plotly_chart(pie_chart, use_container_width=True)
