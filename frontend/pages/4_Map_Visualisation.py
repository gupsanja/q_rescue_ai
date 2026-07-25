import sys
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
from allocation_sim import allocation_ready, get_allocation_result, build_allocation_routes


st.set_page_config(page_title="Sheffield Map Visualisation", page_icon=":world_map:", layout="wide")
apply_global_style()
require_login()

page_header(
    "MP",
    "Sheffield Disaster Map Visualisation",
)

# ── Allocation-driven map (shown when a simulation has been run) ───────────────
if allocation_ready():
    alloc = get_allocation_result()
    scenario = alloc["scenario"]
    routes = build_allocation_routes(alloc)

    incidents_map = {i["id"]: i for i in scenario["incidents"]}
    hospitals_map = {h["id"]: h for h in scenario["hospitals"]}
    ambulances_map = {a["id"]: a for a in scenario["ambulances"]}

    # Severity colours for incident markers
    severity_colors = {
        "LOW": "green",
        "MEDIUM": "blue",
        "HIGH": "orange",
        "CRITICAL": "red",
    }

    # Centre map on mean of all entity positions
    all_lats = (
        [a["lat"] for a in scenario["ambulances"]]
        + [i["lat"] for i in scenario["incidents"]]
        + [h["lat"] for h in scenario["hospitals"]]
    )
    all_lons = (
        [a["lon"] for a in scenario["ambulances"]]
        + [i["lon"] for i in scenario["incidents"]]
        + [h["lon"] for h in scenario["hospitals"]]
    )
    centre_lat = sum(all_lats) / len(all_lats)
    centre_lon = sum(all_lons) / len(all_lons)

    m = folium.Map(location=[centre_lat, centre_lon], zoom_start=12, tiles="OpenStreetMap")

    # Draw assignment routes as polylines (ambulance → incident → hospital)
    for route in routes:
        # Leg 1: Ambulance → Incident
        folium.PolyLine(
            locations=[
                [route["ambulance_lat"], route["ambulance_lon"]],
                [route["incident_lat"], route["incident_lon"]],
            ],
            color="#3b82f6",
            weight=2,
            opacity=0.7,
            tooltip=f"{route['ambulance_id']} → {route['incident_id']}",
            dash_array="6 4",
        ).add_to(m)

        # Leg 2: Incident → Hospital
        if route["hospital_lat"] is not None:
            folium.PolyLine(
                locations=[
                    [route["incident_lat"], route["incident_lon"]],
                    [route["hospital_lat"], route["hospital_lon"]],
                ],
                color="#a855f7",
                weight=2,
                opacity=0.6,
                tooltip=f"{route['incident_id']} → {route['hospital_name']}",
                dash_array="4 6",
            ).add_to(m)

    # Hospital markers
    for hospital in scenario["hospitals"]:
        bed_status = (
            "Critical" if hospital["available_beds"] < 50
            else "Limited" if hospital["available_beds"] < 150
            else "Open"
        )
        color = {"Critical": "red", "Limited": "orange", "Open": "green"}[bed_status]
        folium.Marker(
            location=[hospital["lat"], hospital["lon"]],
            popup=(
                f"<strong>{hospital['name']}</strong><br>"
                f"Beds available: {hospital['available_beds']}/{hospital['capacity']}<br>"
                f"Status: {bed_status}"
            ),
            tooltip=f"{hospital['name']} — {bed_status}",
            icon=folium.Icon(color=color, icon="plus-sign"),
        ).add_to(m)

    # Incident markers (coloured by severity)
    for incident in scenario["incidents"]:
        sev = incident.get("severity_level", "MEDIUM")
        color = severity_colors.get(sev, "blue")
        folium.Marker(
            location=[incident["lat"], incident["lon"]],
            popup=(
                f"<strong>{incident['id']}</strong><br>"
                f"Severity: {sev}<br>"
                f"Category: {incident.get('category', '—')}"
            ),
            tooltip=f"{incident['id']} — {sev}",
            icon=folium.Icon(color=color, icon="warning-sign"),
        ).add_to(m)

    # Ambulance markers (start positions)
    for amb in scenario["ambulances"]:
        folium.Marker(
            location=[amb["lat"], amb["lon"]],
            popup=f"<strong>{amb['id']}</strong><br>Status: {amb.get('status', 'Available')}",
            tooltip=amb["id"],
            icon=folium.Icon(color="blue", icon="road"),
        ).add_to(m)

    # Legend (HTML overlay)
    legend_html = """
    <div style="position:fixed;bottom:30px;left:30px;z-index:1000;background:white;
                padding:12px 16px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.2);
                font-size:13px;line-height:1.8">
        <b>Legend</b><br>
        🔵 Ambulance (start)<br>
        🔴 Critical incident<br>
        🟠 High severity<br>
        🔵 Medium severity<br>
        🟢 Low severity / Hospital (open)<br>
        <span style="color:#3b82f6">— — </span> Response route<br>
        <span style="color:#a855f7">— — </span> Transport to hospital
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    st.subheader("Allocation map — real scenario entities")
    st.caption(
        f"Showing {len(scenario['ambulances'])} ambulances, "
        f"{len(scenario['incidents'])} incidents, "
        f"{len(scenario['hospitals'])} hospitals. "
        f"Routes from QUBO optimal assignment."
    )
    st_folium(m, width=1100, height=580)

    # Summary table
    loc_rows = []
    for h in scenario["hospitals"]:
        loc_rows.append({"Name": h["name"], "Type": "Hospital", "Risk Level": "Low"})
    for i in scenario["incidents"]:
        sev = i.get("severity_level", "MEDIUM")
        risk = {"LOW": "Low", "MEDIUM": "Medium", "HIGH": "High", "CRITICAL": "Critical"}.get(sev, "Medium")
        loc_rows.append({"Name": i["id"], "Type": "Incident", "Risk Level": risk})
    for a in scenario["ambulances"]:
        loc_rows.append({"Name": a["id"], "Type": "Ambulance", "Risk Level": "Low"})

    st.subheader("Scenario Entity Summary")
    render_table(pd.DataFrame(loc_rows))

else:
    # ── Fallback static map (no simulation run yet) ───────────────────────────
    st.info("Run a simulation from **Disaster Input** to see the real allocation map.")

    locations = pd.DataFrame(
        {
            "Name": [
                "Sheffield City Centre",
                "Northern General Hospital",
                "Royal Hallamshire Hospital",
                "Meadowhall",
                "Hillsborough",
                "Darnall",
                "Ecclesall Road",
                "Attercliffe",
            ],
            "Type": [
                "Disaster Zone",
                "Hospital",
                "Hospital",
                "Resource Point",
                "Rescue Centre",
                "High Risk Area",
                "Rescue Centre",
                "High Risk Area",
            ],
            "Latitude": [53.3811, 53.4109, 53.3785, 53.4148, 53.4021, 53.3845, 53.3704, 53.3950],
            "Longitude": [-1.4701, -1.4587, -1.4939, -1.4103, -1.5002, -1.4135, -1.4978, -1.4330],
            "Risk Level": ["Critical", "Low", "Low", "Medium", "High", "High", "Medium", "High"],
        }
    )

    selected_location = st.selectbox("Select Sheffield location", locations["Name"])
    selected_row = locations[locations["Name"] == selected_location].iloc[0]

    st.subheader("Sheffield city response map")

    m = folium.Map(location=[53.3811, -1.4701], zoom_start=12, tiles="OpenStreetMap")

    risk_colors = {"Critical": "red", "High": "orange", "Medium": "blue", "Low": "green"}
    type_icons = {
        "Disaster Zone": "exclamation-triangle",
        "Hospital": "plus-sign",
        "Resource Point": "info-sign",
        "Rescue Centre": "home",
        "High Risk Area": "warning-sign",
    }

    for _, row in locations.iterrows():
        color = risk_colors.get(row["Risk Level"], "blue")
        icon = type_icons.get(row["Type"], "info-sign")
        folium.Marker(
            location=[row["Latitude"], row["Longitude"]],
            popup=(
                f"<strong>{row['Name']}</strong><br>"
                f"Type: {row['Type']}<br>"
                f"Risk: {row['Risk Level']}"
            ),
            tooltip=f"{row['Name']} - {row['Risk Level']}",
            icon=folium.Icon(color=color, icon=icon),
        ).add_to(m)

    folium.Circle(
        location=[selected_row["Latitude"], selected_row["Longitude"]],
        radius=1200,
        popup=f"Selected area: {selected_row['Name']}",
        color=risk_colors.get(selected_row["Risk Level"], "blue"),
        fill=True,
        fill_opacity=0.18,
    ).add_to(m)

    folium.Circle(
        location=[53.3811, -1.4701],
        radius=6500,
        popup="Sheffield city operating area",
        color="#1f8a70",
        fill=False,
        weight=3,
    ).add_to(m)

    st_folium(m, width=1100, height=560)

    st.subheader("Sheffield Location Risk Data")
    render_table(locations[["Name", "Type", "Risk Level"]])
