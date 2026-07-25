import math
import sys
import time as _time
from datetime import datetime
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

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
from allocation_sim import (
    AMBULANCE_SPEED_KMH,
    allocation_ready,
    build_allocation_routes,
    get_allocation_result,
    simulate_ambulance_state,
)
from ambulance_data import available_ambulance_count, build_ambulance_routes


st.set_page_config(
    page_title="Hospital & Ambulance Tracker",
    page_icon=":ambulance:",
    layout="wide",
)
apply_global_style()
require_login()

page_header("A+", "Sheffield Hospital & Ambulance Tracker")

# ── Determine data source ──────────────────────────────────────────────────────
use_allocation = allocation_ready()

if use_allocation:
    alloc = get_allocation_result()
    scenario = alloc["scenario"]
    routes = build_allocation_routes(alloc)
    reference_time = st.session_state.get("allocation_start_time", _time.time())

    hospitals_source = scenario["hospitals"]  # real hospitals from allocation
    hospital_ids = [h["id"] for h in hospitals_source]
    hospital_names = [h["name"] for h in hospitals_source]
else:
    # Fall back to legacy hardcoded data
    fleet_count = available_ambulance_count()
    route_fleet = build_ambulance_routes(fleet_count)

    if fleet_count == 0:
        st.warning("No ambulances are available. Change Available Ambulances in Disaster Input.")
        st.stop()

    hospitals_source = [
        {"id": "H1", "name": "Northern General Hospital", "lat": 53.4109, "lon": -1.4587,
         "capacity": 120, "available_beds": 34},
        {"id": "H2", "name": "Royal Hallamshire Hospital", "lat": 53.3785, "lon": -1.4939,
         "capacity": 95, "available_beds": 22},
        {"id": "H3", "name": "Sheffield Children's Hospital", "lat": 53.3817, "lon": -1.4906,
         "capacity": 55, "available_beds": 16},
        {"id": "H4", "name": "Weston Park Hospital", "lat": 53.3812, "lon": -1.4920,
         "capacity": 40, "available_beds": 9},
        {"id": "H5", "name": "Claremont Hospital", "lat": 53.3682, "lon": -1.5154,
         "capacity": 35, "available_beds": 12},
    ]
    routes = []


# ── Controls ───────────────────────────────────────────────────────────────────
control_col1, control_col2 = st.columns(2)
with control_col1:
    live_refresh = st.toggle("Live refresh", value=True)
with control_col2:
    refresh_seconds = st.selectbox("Refresh every", [5, 10, 15, 30], index=1)


# ── Live tracker fragment ──────────────────────────────────────────────────────
@st.fragment(run_every=refresh_seconds if live_refresh else None)
def live_tracker():
    now = datetime.now()
    updated_time = now.strftime("%H:%M:%S")
    tick = int(now.timestamp() // refresh_seconds)

    if use_allocation:
        # Simulate ambulance states from allocation routes
        amb_rows = []
        hosp_admissions = {}  # hospital_name -> count
        hosp_incoming = {}    # hospital_name -> count

        for idx, route in enumerate(routes):
            state = simulate_ambulance_state(route, reference_time, idx)
            hname = route["hospital_name"]

            # Count admissions / incoming patients dynamically based on simulated state
            if state["phase"] == "idle":
                hosp_admissions[hname] = hosp_admissions.get(hname, 0) + 1
            else:
                hosp_incoming[hname] = hosp_incoming.get(hname, 0) + 1

            amb_rows.append({
                "Ambulance ID": route["ambulance_id"],
                "Current Area": route["incident_id"],
                "Latitude": state["lat"],
                "Longitude": state["lon"],
                "Speed mph": round(state["speed_kmh"] / 1.60934),
                "Availability": state["status"],
                "Assigned Hospital": hname,
                "Progress": f"{state['progress_pct']}%",
                "Updated": updated_time,
            })
        ambulances_df = pd.DataFrame(amb_rows) if amb_rows else pd.DataFrame()

        # Build hospital availability from real scenario data + dynamic admissions
        hosp_rows = []
        for idx, h in enumerate(hospitals_source):
            base_beds = h["available_beds"]
            admitted = hosp_admissions.get(h["name"], 0)
            incoming = hosp_incoming.get(h["name"], 0)

            # Capacity reduces with each added patient who arrives (admitted)
            available = max(0, base_beds - admitted)

            if available <= 10:
                status = "Critical"
            elif available <= 50:
                status = "Limited"
            else:
                status = "Open"

            hosp_rows.append({
                "Hospital": h["name"],
                "Latitude": h["lat"],
                "Longitude": h["lon"],
                "Total Capacity": h["capacity"],
                "Available Beds": available,
                "Admitted Patients": admitted,
                "Incoming Patients": incoming,
                "Status": status,
            })
        hospitals_df = pd.DataFrame(hosp_rows)

        # Incident as focal map point — centre on mean of all incidents
        inc_lats = [i["lat"] for i in scenario["incidents"]]
        inc_lons = [i["lon"] for i in scenario["incidents"]]
        map_centre = [sum(inc_lats) / len(inc_lats), sum(inc_lons) / len(inc_lons)]

        total_spaces = int(hospitals_df["Available Beds"].sum())
        fleet_count = len(routes)

    else:
        # Legacy path — existing animation logic preserved
        base_ambulances = route_fleet.rename(
            columns={
                "Start Location": "Current Area",
                "Start Latitude": "Latitude",
                "Start Longitude": "Longitude",
                "Destination": "Assigned Hospital",
            }
        )[["Ambulance ID", "Current Area", "Latitude", "Longitude", "Assigned Hospital"]]

        def _build_legacy_hospitals(tick):
            rows = []
            for idx, h in enumerate(hospitals_source):
                capacity_val = int(h["capacity"])
                beds_val = int(h["available_beds"])
                available = max(
                    0,
                    min(capacity_val, beds_val + ((tick + idx * 4) % 17) - 8),
                )
                status = "Critical" if available <= 4 else "Limited" if available <= 10 else "Open"
                rows.append({
                    "Hospital": h["name"],
                    "Latitude": h["lat"],
                    "Longitude": h["lon"],
                    "Total Capacity": h["capacity"],
                    "Available Beds": available,
                    "Ambulances": 0,
                    "Status": status,
                })
            return pd.DataFrame(rows)

        def _build_legacy_ambulances(tick):
            ambulances = base_ambulances.copy()
            speeds, statuses, lats, lons = [], [], [], []
            for idx, row in ambulances.iterrows():
                phase = tick + idx * 3
                cycle = phase % 6
                status = "On Route" if cycle in (0, 1, 2) else "Available" if cycle in (3, 4) else "Busy"
                speed = 24 + ((phase * 7) % 28) if status == "On Route" else (0 if status == "Available" else 12 + ((phase * 5) % 18))
                lats.append(round(float(row["Latitude"]) + math.sin(phase * 0.55) * 0.006, 5))
                lons.append(round(float(row["Longitude"]) + math.cos(phase * 0.55) * 0.008, 5))
                speeds.append(speed)
                statuses.append(status)
            ambulances["Latitude"] = lats
            ambulances["Longitude"] = lons
            ambulances["Speed mph"] = speeds
            ambulances["Availability"] = statuses
            ambulances["Progress"] = "—"
            ambulances["Updated"] = updated_time
            return ambulances

        hospitals_df = _build_legacy_hospitals(tick)
        ambulances_df = _build_legacy_ambulances(tick)

        map_centre = [53.3811, -1.4701]
        total_spaces = int(hospitals_df["Available Beds"].sum())
        fleet_count = available_ambulance_count()

    # ── Metrics row ─────────────────────────────────────────────────────────
    metrics = st.columns(4)
    metrics[0].metric("Ambulances Tracked", fleet_count)
    metrics[1].metric("Hospital Spaces", total_spaces)
    metrics[2].metric("Hospitals", len(hospitals_df))
    metrics[3].metric("Updated", updated_time)

    # ── Live map ─────────────────────────────────────────────────────────────
    tracker_map = folium.Map(location=map_centre, zoom_start=12, tiles="OpenStreetMap")

    for _, hosp in hospitals_df.iterrows():
        color = "red" if hosp["Status"] == "Critical" else "orange" if hosp["Status"] == "Limited" else "green"
        folium.Marker(
            location=[hosp["Latitude"], hosp["Longitude"]],
            popup=(
                f"{hosp['Hospital']}<br>"
                f"Beds: {hosp['Available Beds']}/{hosp['Total Capacity']}<br>"
                f"Ambulances: {hosp['Ambulances']}"
            ),
            icon=folium.Icon(color=color, icon="plus-sign"),
        ).add_to(tracker_map)

    if not ambulances_df.empty:
        for _, amb in ambulances_df.iterrows():
            avail = amb.get("Availability", "On Route")
            color = "blue" if avail == "Available" else "purple" if avail == "On Scene" else "red"
            folium.Marker(
                location=[amb["Latitude"], amb["Longitude"]],
                popup=(
                    f"{amb['Ambulance ID']}<br>"
                    f"{avail}<br>"
                    f"{amb.get('Speed mph', 0)} mph"
                ),
                icon=folium.Icon(color=color, icon="road"),
            ).add_to(tracker_map)

    # Show incidents on map too (allocation path only)
    if use_allocation:
        sev_colors = {"LOW": "green", "MEDIUM": "blue", "HIGH": "orange", "CRITICAL": "red"}
        for inc in scenario["incidents"]:
            sev = inc.get("severity_level", "MEDIUM")
            folium.CircleMarker(
                location=[inc["lat"], inc["lon"]],
                radius=6,
                color=sev_colors.get(sev, "blue"),
                fill=True,
                fill_opacity=0.7,
                popup=f"{inc['id']} — {sev}",
                tooltip=inc["id"],
            ).add_to(tracker_map)

    st_folium(tracker_map, width=1200, height=480, key=f"tracker_{tick}")

    # ── Tables ─────────────────────────────────────────────────────────────
    if not ambulances_df.empty:
        st.subheader("Ambulances")
        display_cols = ["Ambulance ID", "Current Area", "Speed mph", "Availability",
                        "Assigned Hospital", "Progress", "Updated"]
        available_cols = [c for c in display_cols if c in ambulances_df.columns]
        render_table(ambulances_df[available_cols])

    st.subheader("Hospitals")
    if use_allocation:
        render_table(hospitals_df[["Hospital", "Total Capacity", "Available Beds", "Admitted Patients", "Incoming Patients", "Status"]])
    else:
        render_table(hospitals_df[["Hospital", "Total Capacity", "Available Beds", "Ambulances", "Status"]])


live_tracker()
