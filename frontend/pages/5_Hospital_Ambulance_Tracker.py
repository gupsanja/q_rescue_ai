import math
from datetime import datetime

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from auth import require_login
from data_sources import build_incident_locations, get_active_simulation_results
from ui_theme import apply_global_style, page_header, render_table

def get_backend_tracker_data(results):
    backend = results["backend_results"]
    allocation = backend["allocation_output"]["scenario"]
    ambulances = pd.DataFrame(
        allocation["ambulances"]
    ).rename(
        columns={
            "id": "Ambulance ID",
            "lat": "Latitude",
            "lon": "Longitude",
            "status": "Availability",
        }
    )
    incidents = pd.DataFrame(
        allocation["incidents"]
    ).rename(
        columns={
            "id": "Incident ID",
            "lat": "Latitude",
            "lon": "Longitude",
            "severity_level": "Severity",
        }
    )
    hospitals = pd.DataFrame(
        allocation["hospitals"]
    ).rename(
        columns={
            "name": "Hospital",
            "lat": "Latitude",
            "lon": "Longitude",
            "capacity": "Total Capacity",
            "available_beds": "Available Beds",
        }
    )
    assignments = pd.DataFrame(
        backend["classical_greedy"]["assignments"]
    )
    return (
        ambulances,
        incidents,
        hospitals,
        assignments,
    )
st.set_page_config(
    page_title="Hospital & Ambulance Tracker",
    page_icon=":ambulance:",
    layout="wide",
)
apply_global_style()
require_login()
page_header("A+", "Sheffield Hospital & Ambulance Tracker")
results = get_active_simulation_results()
st.caption(f"Data source: {results.get('data_source', 'current simulation results')} + frontend/data/disaster_sample_data.csv")
(
    ambulances,
    incidents,
    hospitals,
    assignments,
) = get_backend_tracker_data(results)
fleet_count = len(ambulances)
if fleet_count == 0:
    st.warning(
        "No ambulances are available. Change Available Ambulances in Disaster Input."
    )
    st.stop()
control_col1, control_col2 = st.columns(2)
with control_col1:
    live_refresh = st.toggle("Live refresh", value=False)
with control_col2:
    refresh_seconds = st.selectbox(
        "Refresh every",
        [15, 30, 60],
        index=0,
        disabled=not live_refresh,
    )
if live_refresh:
    st.caption(f"Live map refreshes every {refresh_seconds} seconds.")
else:
    st.info("Live refresh is off for smoother viewing. Turn it on only when you need live updates.")

@st.fragment(run_every=refresh_seconds if live_refresh else None)
def live_tracker():
    updated_at = datetime.now()
    tick = int(updated_at.timestamp() // refresh_seconds)
    updated_time = updated_at.strftime("%H:%M:%S")
    selected_incident = st.selectbox(
        "Incident ID",
        incidents["Incident ID"],
    )
    incident = incidents[
        incidents["Incident ID"] == selected_incident
    ].iloc[0]
    metrics = st.columns(4)
    metrics[0].metric(
        "Severity",
        incident["Severity"]
    )
    metrics[1].metric(
        "Available Beds",
        int(hospitals["Available Beds"].sum())
    )
    metrics[2].metric("Ambulances Available", fleet_count)
    metrics[3].metric("Updated", updated_time)
    tracker_map = folium.Map(
        tiles="OpenStreetMap",
    )

    # Zoom to selected incident
    incident_zoom_points = []
    incident_zoom_points.append(
        [
            incident["Latitude"],
            incident["Longitude"],
        ]
    )

    # Assigned ambulance locations
    for _, assignment in assignments.iterrows():
        if assignment["incident_id"] == selected_incident:
            assigned_ambulance = ambulances[
                ambulances["Ambulance ID"]
                ==
                assignment["ambulance_id"]
            ].iloc[0]
            incident_zoom_points.append(
                [
                    assigned_ambulance["Latitude"],
                    assigned_ambulance["Longitude"],
                ]
            )

    if len(incident_zoom_points) > 1:
        tracker_map.fit_bounds(
            incident_zoom_points,
            padding=(50, 50),
        )
    else:
        tracker_map.fit_bounds(
            [
                [
                    incident["Latitude"] - 0.002,
                    incident["Longitude"] - 0.002,
                ],
                [
                    incident["Latitude"] + 0.002,
                    incident["Longitude"] + 0.002,
                ],
            ]
        )
    for _, incident_row in incidents.iterrows():
        folium.Marker(
            location=[
                incident_row["Latitude"],
                incident_row["Longitude"],
            ],
            popup=(
                f"{incident_row['Incident ID']}<br>"
                f"Severity: {incident_row['Severity']}"
            ),
            icon=folium.Icon(
                color="red",
                icon="warning-sign",
            ),
        ).add_to(tracker_map)
    for _, hospital in hospitals.iterrows():
        folium.Marker(
            location=[
                hospital["Latitude"],
                hospital["Longitude"],
            ],
            popup=(
                f"{hospital['Hospital']}<br>"
                f"Capacity: {hospital['Total Capacity']}<br>"
                f"Available Beds: {hospital['Available Beds']}"
            ),
            icon=folium.Icon(
                color="green",
                icon="plus-sign",
            ),
        ).add_to(tracker_map)
    for _, ambulance in ambulances.iterrows():
        folium.Marker(
            location=[
                ambulance["Latitude"],
                ambulance["Longitude"],
            ],
            popup=(
                f"{ambulance['Ambulance ID']}<br>"
                f"{ambulance['Availability']}"
            ),
            icon=folium.Icon(
                color="blue",
                icon="road",
            ),
        ).add_to(tracker_map)
    for _, assignment in assignments.iterrows():
        ambulance = ambulances[
            ambulances["Ambulance ID"]
            ==
            assignment["ambulance_id"]
        ].iloc[0]
        assigned_incident = incidents[
            incidents["Incident ID"]
            ==
            assignment["incident_id"]
        ].iloc[0]
        folium.PolyLine(
            [
                [
                    ambulance["Latitude"],
                    ambulance["Longitude"],
                ],
                [
                    assigned_incident["Latitude"],
                    assigned_incident["Longitude"],
                ],
            ],
            color="purple",
            weight=3,
            tooltip=(
                f"{assignment['ambulance_id']} → "
                f"{assignment['incident_id']} "
                f"{assignment['distance_km']} km"
            ),
        ).add_to(tracker_map)
    st_folium(tracker_map, width=1000, height=430, key=f"tracker_{tick}")
    st.subheader("Ambulances")
    render_table(
        ambulances[
            [
                "Ambulance ID",
                "Latitude",
                "Longitude",
                "Availability",
            ]
        ]
    )
    st.subheader("Hospitals")
    hospital_table = hospitals.rename(
        columns={
            "Total Capacity": "Total Capacity Metric",
            "Available Beds": "Available Capacity Metric",
        }
    )
    render_table(
        hospital_table[
            [
                "Hospital",
                "Total Capacity Metric",
                "Available Capacity Metric",
            ]
        ]
    )
live_tracker()