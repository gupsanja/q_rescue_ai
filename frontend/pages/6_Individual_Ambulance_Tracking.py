import sys
import time as _time
from datetime import datetime
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from folium.plugins import AntPath
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
    page_title="Individual Ambulance Tracking",
    page_icon=":oncoming_automobile:",
    layout="wide",
)
apply_global_style()
require_login()

page_header("AT", "Individual Ambulance Tracking")

# ── Data source ────────────────────────────────────────────────────────────────
use_allocation = allocation_ready()

if use_allocation:
    alloc = get_allocation_result()
    routes = build_allocation_routes(alloc)
    reference_time = st.session_state.get("allocation_start_time", _time.time())

    if not routes:
        st.warning("No assignments were produced by the allocation solver.")
        st.stop()

    route_ids = [r["ambulance_id"] for r in routes]
    fleet_count = len(routes)

else:
    fleet_count = available_ambulance_count()
    if fleet_count == 0:
        st.warning("No ambulances are available. Change Available Ambulances in Disaster Input.")
        st.stop()
    legacy_routes = build_ambulance_routes(fleet_count)
    route_ids = list(legacy_routes["Ambulance ID"])

st.metric("Ambulances Tracked", fleet_count)

selected_ambulance = st.selectbox("Select ambulance", route_ids)

control_col1, control_col2 = st.columns(2)
with control_col1:
    live_refresh = st.toggle("Live refresh", value=True)
with control_col2:
    refresh_seconds = st.selectbox(
        "Refresh every",
        [3, 5, 10, 15],
        index=1,
        disabled=not live_refresh,
    )

if live_refresh:
    st.caption(f"Live tracking refreshes every {refresh_seconds} seconds.")
else:
    st.info("Live refresh is off. Turn it on to resume automatic tracking.")


@st.fragment(run_every=refresh_seconds if live_refresh else None)
def track_selected_ambulance():
    now = datetime.now()
    tick = int(now.timestamp() // refresh_seconds)

    if use_allocation:
        # ── Allocation-driven tracking ─────────────────────────────────────
        route = next((r for r in routes if r["ambulance_id"] == selected_ambulance), None)
        if route is None:
            st.error(f"Route not found for {selected_ambulance}.")
            return

        route_index = route_ids.index(selected_ambulance)
        state = simulate_ambulance_state(route, reference_time, route_index)

        # Determine trip progress label
        start_label = route["ambulance_id"]
        dest_label = (
            route["incident_id"] if state["phase"] in ("to_incident", "on_scene")
            else route["hospital_name"]
        )

        speed_mph = round(state["speed_kmh"] / 1.60934)
        progress = state["progress_pct"]
        eta_min = max(0, round(state["eta_seconds"] / 60))

        metric_cols = st.columns(5)
        metric_cols[0].metric("Ambulance", route["ambulance_id"])
        metric_cols[1].metric("Status", state["status"])
        metric_cols[2].metric("Speed", f"{speed_mph} mph")
        metric_cols[3].metric("Progress", f"{progress}%")
        metric_cols[4].metric("ETA", f"{eta_min} min")

        st.progress(
            progress / 100,
            text=state["heading_label"],
        )

        # Map — show full two-leg route with current position marker
        amb_pos = [route["ambulance_lat"], route["ambulance_lon"]]
        inc_pos = [route["incident_lat"], route["incident_lon"]]
        hosp_pos = (
            [route["hospital_lat"], route["hospital_lon"]]
            if route["hospital_lat"] is not None
            else inc_pos
        )
        cur_pos = [state["lat"], state["lon"]]

        centre = [(amb_pos[0] + hosp_pos[0]) / 2, (amb_pos[1] + hosp_pos[1]) / 2]
        route_map = folium.Map(location=centre, zoom_start=13, tiles="OpenStreetMap")

        # Leg 1: Ambulance → Incident
        AntPath(
            [amb_pos, inc_pos],
            color="#3b82f6",
            weight=4,
            delay=1000,
            dash_array=[10, 20],
        ).add_to(route_map)

        # Leg 2: Incident → Hospital
        AntPath(
            [inc_pos, hosp_pos],
            color="#a855f7",
            weight=4,
            delay=1200,
            dash_array=[8, 16],
        ).add_to(route_map)

        folium.Marker(amb_pos, popup=f"Start: {route['ambulance_id']}",
                      icon=folium.Icon(color="green", icon="play")).add_to(route_map)
        folium.Marker(inc_pos, popup=f"Incident: {route['incident_id']} ({route['priority']})",
                      tooltip=route["incident_id"],
                      icon=folium.Icon(color="red", icon="warning-sign")).add_to(route_map)
        folium.Marker(hosp_pos, popup=f"Hospital: {route['hospital_name']}",
                      tooltip=route["hospital_name"],
                      icon=folium.Icon(color="green", icon="plus-sign")).add_to(route_map)
        folium.Marker(
            cur_pos,
            popup=(
                f"{route['ambulance_id']}<br>"
                f"Status: {state['status']}<br>"
                f"Speed: {speed_mph} mph<br>"
                f"ETA: {eta_min} min"
            ),
            tooltip=route["ambulance_id"],
            icon=folium.Icon(color="blue", icon="road"),
        ).add_to(route_map)

        st_folium(route_map, width=1200, height=520,
                  key=f"individual_{selected_ambulance}_{tick}")

        trip_df = pd.DataFrame([{
            "Ambulance": route["ambulance_id"],
            "Start": f"A-{route['ambulance_id']} base",
            "Incident": route["incident_id"],
            "Hospital": route["hospital_name"],
            "Priority": route["priority"],
            "Status": state["status"],
            "Speed": f"{speed_mph} mph",
            "Progress": f"{progress}%",
            "ETA": f"{eta_min} min",
            "Updated": now.strftime("%H:%M:%S"),
        }])
        render_table(trip_df)

        # Distance breakdown
        dist_df = pd.DataFrame([{
            "Leg": "Ambulance → Incident",
            "Distance (km)": f"{route['distance_km']:.3f}",
            "Est. Time (min)": f"{route['distance_km'] / (AMBULANCE_SPEED_KMH / 60):.1f}",
        }, {
            "Leg": "Incident → Hospital",
            "Distance (km)": f"{route['hospital_distance_km']:.3f}" if route["hospital_distance_km"] else "—",
            "Est. Time (min)": (
                f"{route['hospital_distance_km'] / (AMBULANCE_SPEED_KMH / 60):.1f}"
                if route["hospital_distance_km"] else "—"
            ),
        }, {
            "Leg": "Total Trip",
            "Distance (km)": f"{route['total_distance_km']:.3f}",
            "Est. Time (min)": f"{route['total_distance_km'] / (AMBULANCE_SPEED_KMH / 60):.1f}",
        }])
        st.subheader("Trip Distance Breakdown")
        render_table(dist_df)

    else:
        # ── Legacy route animation (no allocation result) ──────────────────
        import math

        route_row = legacy_routes[legacy_routes["Ambulance ID"] == selected_ambulance].iloc[0]
        route_index = list(legacy_routes["Ambulance ID"]).index(selected_ambulance)

        progress_val = ((tick * 4) + route_index * 13) % 101
        ratio = progress_val / 100

        current_lat = route_row["Start Latitude"] + (route_row["End Latitude"] - route_row["Start Latitude"]) * ratio
        current_lon = route_row["Start Longitude"] + (route_row["End Longitude"] - route_row["Start Longitude"]) * ratio

        speed = 0 if progress_val == 100 else int(route_row["Base Speed"] + ((tick + route_index) % 9) - 4)

        def _dist_km(a_lat, a_lon, b_lat, b_lon):
            earth_r = 6371
            la1, la2 = math.radians(a_lat), math.radians(b_lat)
            d_la = math.radians(b_lat - a_lat)
            d_lo = math.radians(b_lon - a_lon)
            v = math.sin(d_la / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(d_lo / 2) ** 2
            return earth_r * 2 * math.atan2(math.sqrt(v), math.sqrt(1 - v))

        total_distance = _dist_km(route_row["Start Latitude"], route_row["Start Longitude"],
                                   route_row["End Latitude"], route_row["End Longitude"])
        remaining = total_distance * (1 - ratio)
        eta_min = 0 if speed == 0 else max(1, round((remaining / (speed * 1.60934)) * 60))
        status = "Arrived" if progress_val == 100 else "On Route"

        metric_cols = st.columns(5)
        metric_cols[0].metric("Ambulance", route_row["Ambulance ID"])
        metric_cols[1].metric("Status", status)
        metric_cols[2].metric("Speed", f"{speed} mph")
        metric_cols[3].metric("Progress", f"{progress_val}%")
        metric_cols[4].metric("ETA", f"{eta_min} min")

        st.progress(progress_val / 100, text=f"{route_row['Start Location']} to {route_row['Destination']}")

        centre = [(route_row["Start Latitude"] + route_row["End Latitude"]) / 2,
                  (route_row["Start Longitude"] + route_row["End Longitude"]) / 2]
        route_map = folium.Map(location=centre, zoom_start=13, tiles="OpenStreetMap")

        AntPath(
            [[route_row["Start Latitude"], route_row["Start Longitude"]],
             [current_lat, current_lon],
             [route_row["End Latitude"], route_row["End Longitude"]]],
            color="#ef232a", weight=5, delay=900, dash_array=[10, 18],
        ).add_to(route_map)

        folium.Marker([route_row["Start Latitude"], route_row["Start Longitude"]],
                      popup=f"Start: {route_row['Start Location']}",
                      icon=folium.Icon(color="green", icon="play")).add_to(route_map)
        folium.Marker([route_row["End Latitude"], route_row["End Longitude"]],
                      popup=f"Destination: {route_row['Destination']}",
                      icon=folium.Icon(color="red", icon="plus-sign")).add_to(route_map)
        folium.Marker([current_lat, current_lon],
                      popup=f"{route_row['Ambulance ID']}<br>Speed: {speed} mph<br>ETA: {eta_min} min",
                      tooltip=route_row["Ambulance ID"],
                      icon=folium.Icon(color="blue", icon="road")).add_to(route_map)

        st_folium(route_map, width=1200, height=520,
                  key=f"individual_{selected_ambulance}_{tick}")

        trip_df = pd.DataFrame([{
            "Ambulance": route_row["Ambulance ID"],
            "Start": route_row["Start Location"],
            "Destination": route_row["Destination"],
            "Priority": route_row["Patient Priority"],
            "Status": status,
            "Speed": f"{speed} mph",
            "Progress": f"{progress_val}%",
            "ETA": f"{eta_min} min",
            "Updated": now.strftime("%H:%M:%S"),
        }])
        render_table(trip_df)


track_selected_ambulance()
