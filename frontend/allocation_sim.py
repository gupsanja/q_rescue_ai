"""allocation_sim.py — Shared simulation helpers for QUBO-driven dashboard pages.

Converts the static allocation_output JSON (produced by the QUBO solver pipeline)
into a dynamic "live" simulation by interpolating ambulance positions along their
assigned routes using wall-clock time.

Route phases per ambulance:
  Phase 1 — Start → Incident   (responding at AMBULANCE_SPEED_KMH)
  Phase 2 — On Scene           (stationary, ON_SCENE_SECONDS duration)
  Phase 3 — Incident → Hospital (transporting at AMBULANCE_SPEED_KMH)
  Phase 4 — Returned / Available (back at origin; loop resets)
"""

from __future__ import annotations

import time
from math import asin, cos, radians, sin, sqrt
from typing import Any

import streamlit as st

# ──────────────────────────── constants ────────────────────────────────────────

AMBULANCE_SPEED_KMH: float = 48.0
ON_SCENE_SECONDS: float = 5 * 60  # 5 minutes on scene
LOOP_PAUSE_SECONDS: float = 2 * 60  # 2 minutes idle before repeating


# ──────────────────────────── geometry ─────────────────────────────────────────

def haversine(a: dict[str, float], b: dict[str, float]) -> float:
    """Great-circle distance (km) between two {lat, lon} dicts."""
    lat1, lon1 = radians(a["lat"]), radians(a["lon"])
    lat2, lon2 = radians(b["lat"]), radians(b["lon"])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    val = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(val))


def interpolate(start: dict[str, float], end: dict[str, float], ratio: float) -> dict[str, float]:
    """Linearly interpolate lat/lon between two points at ratio ∈ [0, 1]."""
    return {
        "lat": start["lat"] + (end["lat"] - start["lat"]) * ratio,
        "lon": start["lon"] + (end["lon"] - start["lon"]) * ratio,
    }


# ──────────────────────────── session-state helpers ────────────────────────────

def allocation_ready() -> bool:
    """Return True if a valid allocation result is in session state."""
    result = st.session_state.get("allocation_result")
    if not isinstance(result, dict):
        return False
    return bool(result.get("scenario") and result.get("solvers"))


def get_allocation_result() -> dict[str, Any]:
    """Return the allocation result from session state (call after allocation_ready())."""
    return st.session_state["allocation_result"]  # type: ignore[return-value]


# ──────────────────────────── route building ───────────────────────────────────

def build_allocation_routes(
    allocation_result: dict[str, Any],
    solver: str = "classical-optimal-flow",
) -> list[dict[str, Any]]:
    """Convert solver assignments into a flat list of route dicts for tracker pages.

    Each route dict contains:
        ambulance_id, ambulance_lat, ambulance_lon,
        incident_id, incident_lat, incident_lon, incident_severity,
        hospital_id, hospital_lat, hospital_lon, hospital_name,
        distance_km, hospital_distance_km, total_distance_km, priority
    """
    scenario = allocation_result["scenario"]
    solver_data = allocation_result["solvers"].get(solver, {})
    if solver_data.get("status") != "ok":
        # fall back to first available solver
        for s in allocation_result["solvers"].values():
            if s.get("status") == "ok":
                solver_data = s
                break

    assignments = solver_data.get("assignments", [])

    # Build lookup maps
    ambulances = {a["id"]: a for a in scenario["ambulances"]}
    incidents = {i["id"]: i for i in scenario["incidents"]}
    hospitals = {h["id"]: h for h in scenario["hospitals"]}

    severity_priority = {"LOW": "Low", "MEDIUM": "Medium", "HIGH": "High", "CRITICAL": "Critical"}

    routes = []
    for assignment in assignments:
        amb_id = assignment["ambulance_id"]
        inc_id = assignment["incident_id"]
        hosp_id = assignment.get("hospital_id")

        if amb_id not in ambulances or inc_id not in incidents:
            continue

        amb = ambulances[amb_id]
        inc = incidents[inc_id]
        hosp = hospitals.get(hosp_id) if hosp_id else None

        # If no hospital in assignment, pick any first hospital as destination
        if hosp is None and scenario["hospitals"]:
            hosp = scenario["hospitals"][0]
            hosp_id = hosp["id"]

        hospital_distance = assignment.get("hospital_distance_km")
        if hospital_distance is None and hosp is not None:
            hospital_distance = round(
                haversine(
                    {"lat": inc["lat"], "lon": inc["lon"]},
                    {"lat": hosp["lat"], "lon": hosp["lon"]},
                ),
                3,
            )

        total_distance = round(
            (assignment["distance_km"] or 0) + (hospital_distance or 0), 3
        )

        routes.append({
            "ambulance_id": amb_id,
            "ambulance_lat": amb["lat"],
            "ambulance_lon": amb["lon"],
            "incident_id": inc_id,
            "incident_lat": inc["lat"],
            "incident_lon": inc["lon"],
            "incident_severity": inc.get("severity_level", "MEDIUM"),
            "hospital_id": hosp_id,
            "hospital_lat": hosp["lat"] if hosp else None,
            "hospital_lon": hosp["lon"] if hosp else None,
            "hospital_name": hosp.get("name", hosp_id) if hosp else "Unknown",
            "distance_km": assignment["distance_km"],
            "hospital_distance_km": hospital_distance,
            "total_distance_km": total_distance,
            "priority": severity_priority.get(inc.get("severity_level", "MEDIUM"), "Medium"),
        })

    return routes


# ──────────────────────────── live state simulation ────────────────────────────

def simulate_ambulance_state(
    route: dict[str, Any],
    reference_time: float,
    route_index: int = 0,
) -> dict[str, Any]:
    """Return the current simulated state of one ambulance given its route.

    The simulation loops indefinitely: Phase1 → Phase2 (on scene) →
    Phase3 → Phase4 (idle pause) → repeat.

    Args:
        route:          A route dict from build_allocation_routes().
        reference_time: Unix timestamp used as the start of Phase 1.
        route_index:    Index used to stagger start times so ambulances
                        don't all move in perfect sync.

    Returns a dict with:
        lat, lon       — current position
        status         — "Responding" | "On Scene" | "Transporting" | "Available"
        speed_kmh      — current speed
        progress_pct   — 0–100 overall trip progress (Phases 1+2+3)
        eta_seconds    — seconds until Phase 3 complete (0 when arrived)
        phase          — "to_incident" | "on_scene" | "to_hospital" | "idle"
        heading_label  — human-readable destination description
    """
    speed_ms = AMBULANCE_SPEED_KMH * 1000 / 3600  # metres per second → km/s
    speed_kms = AMBULANCE_SPEED_KMH / 3600         # km per second

    d1 = route["distance_km"] or 0.0
    d3 = route["hospital_distance_km"] or 0.0

    t1 = d1 / speed_kms if speed_kms > 0 else 0.0   # seconds for phase 1
    t2 = ON_SCENE_SECONDS                              # seconds for phase 2
    t3 = d3 / speed_kms if speed_kms > 0 else 0.0   # seconds for phase 3
    t_total = t1 + t2 + t3 + LOOP_PAUSE_SECONDS

    # Stagger start times by route_index × 20 seconds so ambulances appear
    # at different points in their journeys on first load.
    stagger = route_index * 20
    elapsed = (time.time() - reference_time + stagger) % max(t_total, 1.0)

    amb_pos = {"lat": route["ambulance_lat"], "lon": route["ambulance_lon"]}
    inc_pos = {"lat": route["incident_lat"], "lon": route["incident_lon"]}
    hosp_pos = (
        {"lat": route["hospital_lat"], "lon": route["hospital_lon"]}
        if route["hospital_lat"] is not None
        else inc_pos
    )

    if elapsed < t1:
        # Phase 1: Ambulance → Incident
        ratio = elapsed / t1 if t1 > 0 else 1.0
        pos = interpolate(amb_pos, inc_pos, ratio)
        overall_pct = int(ratio * 40)  # phase 1 = 0→40%
        eta = t3 + (t1 - elapsed)     # remaining phase1 + phase3
        return {
            **pos,
            "status": "Responding",
            "speed_kmh": AMBULANCE_SPEED_KMH,
            "progress_pct": overall_pct,
            "eta_seconds": max(0, eta),
            "phase": "to_incident",
            "heading_label": f"→ {route['incident_id']} ({route['priority']})",
        }

    elapsed -= t1

    if elapsed < t2:
        # Phase 2: On Scene
        return {
            **inc_pos,
            "status": "On Scene",
            "speed_kmh": 0.0,
            "progress_pct": 40,
            "eta_seconds": max(0, t3),
            "phase": "on_scene",
            "heading_label": f"On scene at {route['incident_id']}",
        }

    elapsed -= t2

    if elapsed < t3:
        # Phase 3: Incident → Hospital
        ratio = elapsed / t3 if t3 > 0 else 1.0
        pos = interpolate(inc_pos, hosp_pos, ratio)
        overall_pct = 40 + int(ratio * 55)  # phase 3 = 40→95%
        eta = t3 - elapsed
        return {
            **pos,
            "status": "Transporting",
            "speed_kmh": AMBULANCE_SPEED_KMH,
            "progress_pct": overall_pct,
            "eta_seconds": max(0, eta),
            "phase": "to_hospital",
            "heading_label": f"→ {route['hospital_name']}",
        }

    # Phase 4: Idle / returned
    return {
        **hosp_pos,
        "status": "Available",
        "speed_kmh": 0.0,
        "progress_pct": 100,
        "eta_seconds": 0,
        "phase": "idle",
        "heading_label": f"At {route['hospital_name']}",
    }
