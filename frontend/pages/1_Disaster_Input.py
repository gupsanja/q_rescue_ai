from pathlib import Path
import sys

import pandas as pd
import streamlit as st


# Makes utils.py import correctly when this page runs inside Streamlit
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from adapters import (
    DISASTER_CATEGORY_OPTIONS,
    SEVERITY_OPTIONS,
    SHEFFIELD_LOCATIONS,
    to_domain_payload,
)
from auth import require_login
from ui_theme import apply_global_style, page_header
from utils import (
    calculate_disaster_metrics,
    load_latest_simulation_results,
    save_simulation_results,
)


st.set_page_config(page_title="Disaster Input", page_icon=":memo:", layout="wide")
apply_global_style()
require_login()

cached_simulation = load_latest_simulation_results()
if "simulation_results" not in st.session_state and cached_simulation:
    st.session_state["simulation_results"] = cached_simulation

if st.session_state.get("simulation_results", {}).get("restored_from_cache"):
    saved_at = st.session_state["simulation_results"].get("cache_saved_at", "recently")
    st.info(
        f"Recent simulation restored from local demo cache ({saved_at}). "
        "This is temporary frontend storage until backend database persistence is connected."
    )


def initialise_synced_value(field_key, default):
    manual_key = f"{field_key}_manual"
    slider_key = f"{field_key}_slider"

    if manual_key not in st.session_state:
        st.session_state[manual_key] = default
    if slider_key not in st.session_state:
        st.session_state[slider_key] = default


def copy_manual_to_slider(field_key):
    st.session_state[f"{field_key}_slider"] = st.session_state[f"{field_key}_manual"]


def copy_slider_to_manual(field_key):
    st.session_state[f"{field_key}_manual"] = st.session_state[f"{field_key}_slider"]


def synced_manual_slider(label, field_key, minimum, maximum, default, slider_step, help_text):
    initialise_synced_value(field_key, default)

    manual_key = f"{field_key}_manual"
    slider_key = f"{field_key}_slider"

    manual_col, enter_col, slider_col = st.columns([1.05, 0.38, 2.1])

    with manual_col:
        st.number_input(
            f"Manual {label.lower()}",
            min_value=minimum,
            max_value=maximum,
            step=1,
            key=manual_key,
            help="Type the exact value here, then press Enter.",
        )

    with enter_col:
        st.write("")
        st.write("")
        if st.button("Enter", key=f"{field_key}_enter", use_container_width=True):
            copy_manual_to_slider(field_key)

    with slider_col:
        st.slider(
            label,
            min_value=minimum,
            max_value=maximum,
            step=slider_step,
            key=slider_key,
            help=help_text,
            on_change=copy_slider_to_manual,
            args=(field_key,),
        )

    return st.session_state[slider_key]


page_header(
    "DR",
    "Disaster Scenario Input",
)

with st.container(border=True):
    st.subheader("Scenario details")

    detail_col1, detail_col2, detail_col3 = st.columns(3)

    with detail_col1:
        disaster_type = st.selectbox(
            "Select disaster category",
            list(DISASTER_CATEGORY_OPTIONS.keys()),
            help="Uses the same category values as the backend domain model.",
        )

    with detail_col2:
        custom_disaster_type = st.text_input(
            "Scenario note",
            value="",
            placeholder="Optional UI note",
            help="Optional frontend note. The backend category remains the selected canonical value.",
        )

    with detail_col3:
        location = st.selectbox(
            "Sheffield location",
            list(SHEFFIELD_LOCATIONS.keys()),
        )

    custom_location = st.text_input(
        "Location note",
        value="",
        placeholder="Optional: street, ward, or extra Sheffield detail",
    )

    st.divider()
    st.subheader("Impact and available resources")

    severity = synced_manual_slider(
        "Disaster severity level",
        "severity",
        1,
        4,
        3,
        1,
        "Backend scale: 1 Low, 2 Medium, 3 High, 4 Critical.",
    )
    severity_label = next(
        label for label, value in SEVERITY_OPTIONS.items() if int(value) == int(severity)
    )
    st.caption(f"Selected backend severity: {severity_label.upper()} ({severity})")

    affected_population = synced_manual_slider(
        "Affected population",
        "affected_population",
        0,
        1000000,
        25000,
        1,
        "Estimated number of people affected by the scenario.",
    )

    available_ambulances = synced_manual_slider(
        "Available ambulances",
        "available_ambulances",
        0,
        100,
        15,
        1,
        "Ambulances available for response planning.",
    )

    available_rescue_teams = synced_manual_slider(
        "Available rescue teams",
        "available_rescue_teams",
        0,
        100,
        10,
        1,
        "Rescue teams available for response planning.",
    )

    available_food_units = synced_manual_slider(
        "Available food supply units",
        "available_food_units",
        0,
        500,
        80,
        1,
        "Food supply units available for affected people.",
    )

    submitted = st.button("Run Simulation", use_container_width=True)

if submitted:
    final_disaster_type = disaster_type
    final_location = location

    results = calculate_disaster_metrics(
        severity,
        affected_population,
        available_ambulances,
        available_rescue_teams,
        available_food_units,
    )

    simulation_results = {
        "disaster_type": final_disaster_type,
        "disaster_note": custom_disaster_type.strip(),
        "location": final_location,
        "location_note": custom_location.strip(),
        "severity": severity,
        "affected_population": affected_population,
        "available_ambulances": available_ambulances,
        "available_rescue_teams": available_rescue_teams,
        "available_food_units": available_food_units,
        **results,
    }
    simulation_results["domain_payload"] = to_domain_payload(simulation_results)
    save_simulation_results(simulation_results)
    st.session_state["simulation_results"] = simulation_results

    st.success("Simulation completed successfully. Go to the Results page.")

    results_table = pd.DataFrame(
        {
            "Metric": [
                "Disaster Type",
                "Location",
                "Severity",
                "Backend Category",
                "Affected Population",
                "Available Ambulances",
                "Available Rescue Teams",
                "Available Food Units",
                "Estimated Casualties",
                "Response Time",
                "Resources Needed",
                "Optimisation Score",
                "Recommended Ambulances",
                "Recommended Rescue Teams",
                "Recommended Food Units",
                "Critical Risk",
                "High Risk",
                "Medium Risk",
                "Low Risk",
            ],
            "Metric Value": [
                final_disaster_type,
                final_location,
                f"{severity_label} ({severity})",
                simulation_results["domain_payload"]["incident"]["category"],
                f"{affected_population:,}",
                available_ambulances,
                available_rescue_teams,
                available_food_units,
                f"{results['estimated_casualties']:,}",
                f"{results['response_time']} min",
                results["resources_needed"],
                f"{results['optimisation_score']}%",
                results["recommended_ambulances"],
                results["recommended_rescue_teams"],
                results["recommended_food_units"],
                f"{results['critical_risk']}%",
                f"{results['high_risk']}%",
                f"{results['medium_risk']}%",
                f"{results['low_risk']}%",
            ],
        }
    )

    st.subheader("Simulation Results")
    st.dataframe(results_table, use_container_width=True, hide_index=True)
