import pandas as pd
import plotly.express as px
import streamlit as st

from auth import require_login
from ui_theme import apply_global_style, page_header, render_table


st.set_page_config(page_title="Comparison View", page_icon=":balance_scale:", layout="wide")
apply_global_style()
require_login()

page_header("QO", "Optimisation Comparison")

st.markdown(
    """
    <style>
        .comparison-section-heading {
            margin: 1.15rem 0 0.75rem 0;
            padding: 0.9rem 1.1rem;
            border-left: 8px solid #ffffff;
            border-radius: 6px;
            background: linear-gradient(90deg, #ef232a, #7a1016);
            color: #ffffff !important;
            font-size: 1.28rem;
            font-weight: 950;
            letter-spacing: 0.02rem;
            text-transform: uppercase;
            box-shadow: 0 10px 24px rgba(239, 35, 42, 0.30);
        }

        .comparison-help-text {
            margin: -0.25rem 0 0.85rem 0;
            color: #ffffff !important;
            font-weight: 750;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def section_heading(title, note=None):
    st.markdown(
        f'<div class="comparison-section-heading">{title}</div>',
        unsafe_allow_html=True,
    )
    if note:
        st.markdown(
            f'<p class="comparison-help-text">{note}</p>',
            unsafe_allow_html=True,
        )


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

section_heading("Metric Comparison Table")
comparison_table = comparison.rename(
    columns={
        "Unit": "Metric Unit",
        "Classical": "Classical Metric Value",
        "Quantum": "Quantum Metric Value",
    }
)
render_table(comparison_table)

line_data = comparison.melt(
    id_vars=["Metric", "Unit", "Better When"],
    value_vars=["Classical", "Quantum"],
    var_name="Method",
    value_name="Metric Value",
)

section_heading(
    "Line Plot Graph",
    "The line chart compares Classical and Quantum values across each metric.",
)
line_chart = px.line(
    line_data,
    x="Metric",
    y="Metric Value",
    color="Method",
    markers=True,
    title="Classical vs Quantum Metric Trend",
    color_discrete_map={"Classical": "#ef232a", "Quantum": "#f2f2f2"},
)
line_chart.update_traces(line=dict(width=4), marker=dict(size=11))
line_chart.update_layout(
    paper_bgcolor="#221f27",
    plot_bgcolor="#221f27",
    font=dict(color="#ffffff", size=14),
    title=dict(
        font=dict(color="#ffffff", size=24),
        x=0.03,
        xanchor="left",
    ),
    xaxis=dict(
        title="Metric",
        title_font=dict(color="#ffffff", size=16),
        tickfont=dict(color="#ffffff", size=13),
        gridcolor="rgba(255, 255, 255, 0.14)",
    ),
    yaxis=dict(
        title="Metric Value",
        title_font=dict(color="#ffffff", size=16),
        tickfont=dict(color="#ffffff", size=13),
        gridcolor="rgba(255, 255, 255, 0.18)",
    ),
    legend=dict(
        title="Method",
        font=dict(color="#ffffff", size=13),
        title_font=dict(color="#ffffff", size=13),
        orientation="h",
        yanchor="bottom",
        y=1.04,
        xanchor="right",
        x=1,
    ),
    margin=dict(l=60, r=40, t=90, b=70),
)

st.plotly_chart(line_chart, use_container_width=True)

section_heading("Chart Breakdown")
bar_chart = px.bar(
    comparison,
    x="Metric",
    y=["Classical", "Quantum"],
    barmode="group",
    title="Classical vs Quantum Bar Chart",
    color_discrete_sequence=["#ef232a", "#f2f2f2"],
)
bar_chart.update_layout(
    plot_bgcolor="#221f27",
    paper_bgcolor="#221f27",
    font=dict(color="#ffffff", size=13),
    title=dict(font=dict(color="#ffffff", size=21), x=0.03, xanchor="left"),
    xaxis=dict(title="Metric", tickfont=dict(color="#ffffff")),
    yaxis=dict(title="Metric Value", tickfont=dict(color="#ffffff")),
    legend=dict(font=dict(color="#ffffff"), title_font=dict(color="#ffffff")),
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
    font=dict(color="#ffffff", size=13),
    title=dict(font=dict(color="#ffffff", size=21), x=0.03, xanchor="left"),
    legend=dict(font=dict(color="#ffffff"), title_font=dict(color="#ffffff")),
)

chart_col1, chart_col2 = st.columns(2)
with chart_col1:
    st.plotly_chart(bar_chart, use_container_width=True)
with chart_col2:
    st.plotly_chart(pie_chart, use_container_width=True)
