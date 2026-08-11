from pathlib import Path

import streamlit as st

from q_rescue.services.application_service import run_application_workflow
from q_rescue.simulation.generator import generate_scenario


st.set_page_config(page_title="Q-Rescue AI", layout="wide")
st.title("Q-Rescue AI")
st.caption("Simulation → AI prediction → classical baseline → quantum allocation → shared metrics")

seed = st.sidebar.number_input("Scenario seed", min_value=0, value=42)
ambulance_count = st.sidebar.slider("Ambulances", 1, 10, 3)
incident_count = st.sidebar.slider("Incidents", 1, 20, 5)

scenario = generate_scenario(ambulance_count, incident_count, seed=int(seed))
if ambulance_count * incident_count > 24:
    st.warning(
        "The exact QUBO solver supports at most 24 binary variables. "
        "Reduce ambulances × incidents, or enable the QAOA adapter for larger scenarios."
    )

model_dir = Path("flood_xgboost_project/outputs")
workflow = run_application_workflow(
    scenario,
    model_dir=model_dir if model_dir.exists() else None,
    run_ai=scenario.category.value == "flood",
    run_quantum=ambulance_count * incident_count <= 24,
)

prediction = workflow["prediction"]
st.subheader("AI Prediction Layer")
st.write(f"Status: **{prediction['status']}**")
if prediction["status"] == "ok":
    aggregate = prediction["dashboard_payload"]["aggregate"]
    st.metric("Dominant predicted severity", aggregate["dominant_severity"])
    st.metric("Mean predicted demand", aggregate["mean_resource_demand"])
else:
    st.info(prediction.get("reason", "AI prediction was not run."))

st.subheader("Allocation comparison")
allocation = workflow["allocation"]
for name in ("classical_baseline", "classical_optimal", "quantum"):
    payload = allocation[name]
    with st.container(border=True):
        st.subheader(name.replace("_", " ").title())
        if payload.get("status") != "ok":
            st.info(payload.get("reason", payload.get("status", "unavailable")))
            continue
        result_cols = st.columns(3)
        result_cols[0].metric("Objective", f"{payload['objective_value']:.2f}")
        result_cols[1].metric("Coverage", f"{payload['metrics']['coverage_percent']:.1f}%")
        result_cols[2].metric(
            "Critical coverage",
            f"{payload['metrics']['critical_coverage_percent']:.1f}%",
        )
        st.dataframe(payload["assignments"], width="stretch")

with st.expander("Shared integration contract"):
    st.json(workflow)
