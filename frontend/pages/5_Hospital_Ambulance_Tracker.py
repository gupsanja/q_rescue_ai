import math
from datetime import datetime

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from ambulance_data import available_ambulance_count, build_ambulance_routes
from auth import require_login
from ui_theme import apply_global_style, page_header, render_table


st.set_page_config(
    page_title="Hospital & Ambulance Tracker",
    page_icon=":ambulance:",
    layout="wide",
)
apply_global_style()
require_login()

page_header("A+", "Sheffield Hospital & Ambulance Tracker")

incident_locations = pd.DataFrame(
    {
        "Incident Location": [
            "Sheffield City Centre",
            "Meadowhall",
            "Hillsborough",
            "Darnall",
            "Attercliffe",
            "Ecclesall Road",
        ],
        "Latitude": [53.3811, 53.4148, 53.4021, 53.3845, 53.3950, 53.3704],
        "Longitude": [-1.4701, -1.4103, -1.5002, -1.4135, -1.4330, -1.4978],
        "Incident Type": ["Accident", "Flood", "Fire", "Accident", "Chemical", "Medical"],
        "Priority": ["Critical", "High", "High", "Medium", "Critical", "Medium"],
    }
)

base_hospitals = pd.DataFrame(
    {
        "Hospital": [
            "Northern General Hospital",
            "Royal Hallamshire Hospital",
            "Sheffield Children's Hospital",
            "Weston Park Hospital",
            "Claremont Hospital",
        ],
        "Latitude": [53.4109, 53.3785, 53.3817, 53.3812, 53.3682],
        "Longitude": [-1.4587, -1.4939, -1.4906, -1.4920, -1.5154],
        "Total Spaces": [120, 95, 55, 40, 35],
        "Base Spaces": [34, 22, 16, 9, 12],
        "Base Ambulances": [8, 6, 3, 2, 2],
    }
)

fleet_count = available_ambulance_count()
route_fleet = build_ambulance_routes(fleet_count)

if fleet_count == 0:
    st.warning("No ambulances are available. Change Available Ambulances in Disaster Input.")
    st.stop()

base_ambulances = route_fleet.rename(
    columns={
        "Start Location": "Current Area",
        "Start Latitude": "Latitude",
        "Start Longitude": "Longitude",
        "Destination": "Assigned Hospital",
    }
)[
    [
        "Ambulance ID",
        "Current Area",
        "Latitude",
        "Longitude",
        "Assigned Hospital",
    ]
]


def build_live_hospital_data(base_data, ambulance_data, tick):
    hospitals = base_data.copy()
    spaces = []
    statuses = []
    assigned_counts = ambulance_data["Assigned Hospital"].value_counts()

    for index, row in hospitals.iterrows():
        available_spaces = max(
            0,
            min(
                int(row["Total Spaces"]),
                int(row["Base Spaces"]) + ((tick + index * 4) % 17) - 8,
            ),
        )
        if available_spaces <= 4:
            status = "Critical"
        elif available_spaces <= 10:
            status = "Limited"
        else:
            status = "Open"

        spaces.append(available_spaces)
        statuses.append(status)

    hospitals["Available Spaces"] = spaces
    hospitals["Ambulances Available"] = (
        hospitals["Hospital"].map(assigned_counts).fillna(0).astype(int)
    )
    hospitals["Status"] = statuses
    return hospitals.drop(columns=["Base Spaces", "Base Ambulances"])


def build_live_ambulance_data(base_data, tick, updated_time):
    ambulances = base_data.copy()
    speeds = []
    statuses = []
    latitudes = []
    longitudes = []

    for index, row in ambulances.iterrows():
        phase = tick + index * 3
        status_cycle = phase % 6

        if status_cycle in (0, 1, 2):
            status = "On Route"
            speed = 24 + ((phase * 7) % 28)
        elif status_cycle in (3, 4):
            status = "Available"
            speed = 0
        else:
            status = "Busy"
            speed = 12 + ((phase * 5) % 18)

        latitudes.append(round(float(row["Latitude"]) + math.sin(phase * 0.55) * 0.006, 5))
        longitudes.append(round(float(row["Longitude"]) + math.cos(phase * 0.55) * 0.008, 5))
        speeds.append(speed)
        statuses.append(status)

    ambulances["Latitude"] = latitudes
    ambulances["Longitude"] = longitudes
    ambulances["Speed mph"] = speeds
    ambulances["Availability"] = statuses
    ambulances["Updated"] = updated_time
    return ambulances


control_col1, control_col2 = st.columns(2)
with control_col1:
    live_refresh = st.toggle("Live refresh", value=True)
with control_col2:
    refresh_seconds = st.selectbox("Refresh every", [5, 10, 15, 30], index=1)


@st.fragment(run_every=refresh_seconds if live_refresh else None)
def live_tracker():
    updated_at = datetime.now()
    tick = int(updated_at.timestamp() // refresh_seconds)
    updated_time = updated_at.strftime("%H:%M:%S")

    selected_location = st.selectbox(
        "Incident location",
        incident_locations["Incident Location"],
    )
    incident = incident_locations[
        incident_locations["Incident Location"] == selected_location
    ].iloc[0]

    ambulances = build_live_ambulance_data(base_ambulances, tick, updated_time)
    hospitals = build_live_hospital_data(base_hospitals, ambulances, tick)

    metrics = st.columns(4)
    metrics[0].metric("Priority", incident["Priority"])
    metrics[1].metric("Hospital Spaces", int(hospitals["Available Spaces"].sum()))
    metrics[2].metric("Ambulances Available", fleet_count)
    metrics[3].metric("Updated", updated_time)

    tracker_map = folium.Map(
        location=[incident["Latitude"], incident["Longitude"]],
        zoom_start=12,
        tiles="OpenStreetMap",
    )

    folium.Marker(
        location=[incident["Latitude"], incident["Longitude"]],
        popup=f"{incident['Incident Location']} - {incident['Priority']}",
        icon=folium.Icon(color="red", icon="warning-sign"),
    ).add_to(tracker_map)

    for _, hospital in hospitals.iterrows():
        color = "red" if hospital["Status"] == "Critical" else "orange" if hospital["Status"] == "Limited" else "green"
        folium.Marker(
            location=[hospital["Latitude"], hospital["Longitude"]],
            popup=(
                f"{hospital['Hospital']}<br>"
                f"Spaces: {hospital['Available Spaces']}<br>"
                f"Ambulances: {hospital['Ambulances Available']}"
            ),
            icon=folium.Icon(color=color, icon="plus-sign"),
        ).add_to(tracker_map)

    for _, ambulance in ambulances.iterrows():
        color = "blue" if ambulance["Availability"] == "Available" else "purple"
        folium.Marker(
            location=[ambulance["Latitude"], ambulance["Longitude"]],
            popup=(
                f"{ambulance['Ambulance ID']}<br>"
                f"{ambulance['Availability']}<br>"
                f"{ambulance['Speed mph']} mph"
            ),
            icon=folium.Icon(color=color, icon="road"),
        ).add_to(tracker_map)

    st_folium(tracker_map, width=1200, height=480, key=f"tracker_{tick}")

    st.subheader("Ambulances")
    ambulance_table = ambulances.rename(
        columns={
            "Speed mph": "Speed Metric (mph)",
            "Updated": "Last Updated",
        }
    )
    render_table(
        ambulance_table[
            [
                "Ambulance ID",
                "Current Area",
                "Speed Metric (mph)",
                "Availability",
                "Assigned Hospital",
                "Last Updated",
            ]
        ]
    )

    st.subheader("Hospitals")
    hospital_table = hospitals.rename(
        columns={
            "Total Spaces": "Total Capacity Metric",
            "Available Spaces": "Available Capacity Metric",
            "Ambulances Available": "Ambulance Count Metric",
        }
    )
    render_table(
        hospital_table[
            [
                "Hospital",
                "Total Capacity Metric",
                "Available Capacity Metric",
                "Ambulance Count Metric",
                "Status",
            ]
        ]
    )


live_tracker()
