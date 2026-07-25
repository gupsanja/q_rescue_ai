import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Makes local modules import correctly when this page runs inside Streamlit
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

# Backend allocation service (src/ package must be on the path)
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from auth import require_login
from ui_theme import apply_global_style, page_header, render_table
from allocation_sim import allocation_ready, get_allocation_result


st.set_page_config(page_title="Results Dashboard", page_icon=":bar_chart:", layout="wide")
apply_global_style()
require_login()

page_header("RS", "Simulation Results")

if "simulation_results" not in st.session_state:
    st.warning("Run a simulation from Disaster Input first.")
    st.stop()

results = st.session_state["simulation_results"]

# ── Section 1: Population-level simulation metrics (formula-based) ─────────────
summary = pd.DataFrame(
    {
        "Result": [
            "Disaster Type",
            "Location",
            "Severity",
            "Affected Population",
            "Estimated Casualties",
            "Response Time",
            "Resources Needed",
            "Optimisation Score",
        ],
        "Value": [
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
        "Resource": ["Ambulances", "Rescue Teams", "Food Units"],
        "Available": [
            results["available_ambulances"],
            results["available_rescue_teams"],
            results["available_food_units"],
        ],
        "Recommended": [
            results["recommended_ambulances"],
            results["recommended_rescue_teams"],
            results["recommended_food_units"],
        ],
    }
)

risk = pd.DataFrame(
    {
        "Risk Level": ["Low", "Medium", "High", "Critical"],
        "Percentage": [
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

# ── Section 2: QUBO Allocation Results ────────────────────────────────────────
if not allocation_ready():
    st.info("Re-run the simulation to load QUBO allocation results on this page.")
    st.stop()

st.divider()
st.subheader("⚛ QUBO Allocation Results")

alloc = get_allocation_result()
scenario = alloc["scenario"]
solvers = alloc["solvers"]
opt = alloc["optimization"]

# KPI row from the primary solver
primary = solvers.get("classical-optimal-flow", {})
metrics = primary.get("metrics", {})
assignments = primary.get("assignments", [])

kpi_cols = st.columns(4)
kpi_cols[0].metric("Ambulances Dispatched", len(assignments))
kpi_cols[1].metric("Incidents in Scenario", scenario["counts"]["incidents"])
kpi_cols[2].metric(
    "Avg Response Distance",
    f"{metrics.get('average_distance_km', 0):.2f} km",
)
kpi_cols[3].metric(
    "Critical Coverage",
    f"{metrics.get('critical_coverage_percent', 0):.0f}%",
)

# Solver comparison table
solver_rows = []
for solver_name, solver_data in solvers.items():
    if solver_data.get("status") != "ok":
        solver_rows.append({
            "Solver": solver_name,
            "Status": solver_data.get("status", "unknown"),
            "QUBO Energy": "—",
            "Avg Distance (km)": "—",
            "Coverage %": "—",
            "Critical Coverage %": "—",
            "Runtime (s)": "—",
        })
        continue
    m = solver_data.get("metrics", {})
    solver_rows.append({
        "Solver": solver_name,
        "Status": "✓ ok",
        "QUBO Energy": f"{solver_data.get('qubo_energy', 0):.4f}",
        "Avg Distance (km)": f"{m.get('average_distance_km', 0):.3f}",
        "Coverage %": f"{m.get('coverage_percent', 0):.1f}",
        "Critical Coverage %": f"{m.get('critical_coverage_percent', 0):.1f}",
        "Runtime (s)": f"{solver_data.get('runtime_seconds', 0):.4f}",
    })

st.subheader("Solver Comparison")
render_table(pd.DataFrame(solver_rows))

# Assignment table
if assignments:
    # Build lookup maps
    incidents_map = {i["id"]: i for i in scenario["incidents"]}
    hospitals_map = {h["id"]: h for h in scenario["hospitals"]}
    ambulances_map = {a["id"]: a for a in scenario["ambulances"]}

    assignment_rows = []
    for asn in assignments:
        inc = incidents_map.get(asn["incident_id"], {})
        hosp = hospitals_map.get(asn.get("hospital_id"), {})
        assignment_rows.append({
            "Ambulance": asn["ambulance_id"],
            "Incident": asn["incident_id"],
            "Severity": inc.get("severity_level", "—"),
            "Distance to Incident (km)": f"{asn.get('distance_km', 0):.3f}",
            "Hospital": hosp.get("name", asn.get("hospital_id", "—")),
            "Distance to Hospital (km)": (
                f"{asn['hospital_distance_km']:.3f}"
                if asn.get("hospital_distance_km") is not None
                else "—"
            ),
        })

    st.subheader("Optimal Assignments (classical-optimal-flow)")
    render_table(pd.DataFrame(assignment_rows))

# Quantum advantage summary (gaps from exact, if available)
gaps = opt.get("gaps_from_exact", {})
if any(v is not None for v in gaps.values()):
    st.subheader("Gap from Exact Solution")
    gap_rows = [
        {
            "Solver": "Classical Greedy",
            "Absolute Gap": gaps.get("classical_greedy"),
            "Relative Gap (%)": gaps.get("classical_greedy_percent"),
        },
        {
            "Solver": "Classical Optimal Flow",
            "Absolute Gap": gaps.get("classical_optimal_flow"),
            "Relative Gap (%)": gaps.get("classical_optimal_flow_percent"),
        },
        {
            "Solver": "QAOA",
            "Absolute Gap": gaps.get("qaoa"),
            "Relative Gap (%)": gaps.get("qaoa_percent"),
        },
    ]
    formatted_gaps = []
    for row in gap_rows:
        formatted_gaps.append({
            "Solver": row["Solver"],
            "Absolute Gap": f"{row['Absolute Gap']:.4f}" if row["Absolute Gap"] is not None else "—",
            "Relative Gap (%)": f"{row['Relative Gap (%)']:.2f}%" if row["Relative Gap (%)"] is not None else "—",
        })
    render_table(pd.DataFrame(formatted_gaps))
