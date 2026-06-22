import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from auth import require_login
from ui_theme import apply_global_style, page_header, render_table


st.set_page_config(page_title="Sheffield Map Visualisation", page_icon=":world_map:", layout="wide")
apply_global_style()
require_login()

page_header(
    "MP",
    "Sheffield Disaster Map Visualisation",
)

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
        "Latitude": [
            53.3811,
            53.4109,
            53.3785,
            53.4148,
            53.4021,
            53.3845,
            53.3704,
            53.3950,
        ],
        "Longitude": [
            -1.4701,
            -1.4587,
            -1.4939,
            -1.4103,
            -1.5002,
            -1.4135,
            -1.4978,
            -1.4330,
        ],
        "Risk Level": [
            "Critical",
            "Low",
            "Low",
            "Medium",
            "High",
            "High",
            "Medium",
            "High",
        ],
    }
)

selected_location = st.selectbox("Select Sheffield location", locations["Name"])
selected_row = locations[locations["Name"] == selected_location].iloc[0]

st.subheader("Sheffield city response map")

m = folium.Map(
    location=[53.3811, -1.4701],
    zoom_start=12,
    tiles="OpenStreetMap",
)

risk_colors = {
    "Critical": "red",
    "High": "orange",
    "Medium": "blue",
    "Low": "green",
}

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
