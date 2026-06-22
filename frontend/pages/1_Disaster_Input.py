from pathlib import Path
import sys

import pandas as pd
import streamlit as st


# Makes utils.py import correctly when this page runs inside Streamlit
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from utils import calculate_disaster_metrics
from auth import require_login
from ui_theme import apply_global_style, page_header


st.set_page_config(page_title="Disaster Input", page_icon=":memo:", layout="wide")
apply_global_style()
require_login()


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
            "Select disaster type",
            ["Flood", "Earthquake", "Fire", "Cyclone", "Accident", "Other"],
        )

    with detail_col2:
        custom_disaster_type = st.text_input(
            "Other disaster type",
            value="",
            placeholder="Optional",
            help="Use this only when you select Other.",
        )

    with detail_col3:
        location = st.selectbox(
            "Sheffield location",
            [
                "Sheffield City Centre",
                "Northern General Hospital",
                "Royal Hallamshire Hospital",
                "Meadowhall",
                "Hillsborough",
                "Darnall",
                "Ecclesall Road",
                "Attercliffe",
                "Other Sheffield area",
            ],
        )

    custom_location = ""
    if location == "Other Sheffield area":
        custom_location = st.text_input(
            "Enter Sheffield area",
            value="",
            placeholder="Example: Manor, Walkley, Crookes",
        )

    st.divider()
    st.subheader("Impact and available resources")

    severity = synced_manual_slider(
        "Disaster severity level",
        "severity",
        0,
        10,
        6,
        1,
        "0 means no impact and 10 means critical impact.",
    )

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
    validation_errors = []

    final_disaster_type = custom_disaster_type.strip() if disaster_type == "Other" else disaster_type

    if disaster_type == "Other" and not final_disaster_type:
        validation_errors.append("Please enter the other disaster type.")

    final_location = custom_location.strip() if location == "Other Sheffield area" else location

    if not final_location:
        validation_errors.append("Please enter the Sheffield area.")

    if validation_errors:
        for error in validation_errors:
            st.error(error)
        st.stop()

    results = calculate_disaster_metrics(
        severity,
        affected_population,
        available_ambulances,
        available_rescue_teams,
        available_food_units,
    )

    st.session_state["simulation_results"] = {
        "disaster_type": final_disaster_type,
        "location": final_location,
        "severity": severity,
        "affected_population": affected_population,
        "available_ambulances": available_ambulances,
        "available_rescue_teams": available_rescue_teams,
        "available_food_units": available_food_units,
        **results,
    }

    st.success("Simulation completed successfully. Go to the Results page.")

    results_table = pd.DataFrame(
        {
            "Result": [
                "Disaster Type",
                "Location",
                "Severity",
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
            "Value": [
                final_disaster_type,
                final_location,
                severity,
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
