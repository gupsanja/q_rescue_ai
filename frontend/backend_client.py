from pathlib import Path
import sys

from adapters import category_from_label

SRC_DIR = Path(__file__).resolve().parents[1] / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from q_rescue.services.allocation_output import build_allocation_output_from_request

def run_backend_simulation(
    disaster_type,
    severity,
    affected_population,
    available_ambulances,
    available_rescue_teams,
    available_food_units,
):
    request = {
        "scenario": {
            "category": category_from_label(disaster_type).value,
            "ambulance_count": available_ambulances,
            "incident_count": max(1, affected_population // 5000),
            "seed": 42,
            "use_sheffield_coords": True,
        },
        "optimisation": {
            "critical_priority": True,
            "run_qaoa": True,
        },
        "ui_context": {
            "severity": severity,
            "affected_population": affected_population,
            "available_rescue_teams": available_rescue_teams,
            "available_food_units": available_food_units,
        },
    }
    backend_output = build_allocation_output_from_request(request)
    return convert_backend_output_to_frontend_metrics(
        backend_output,
        severity,
        affected_population,
        available_ambulances,
        available_rescue_teams,
        available_food_units,
    )

def solver_to_dashboard_metrics(solver_output):
    """
    Convert raw solver assignment output into dashboard-friendly metrics.
    """
    assignments = solver_output.get("assignments", [])
    if not assignments:
        return {
            "response_time": 0,
            "ambulances": 0,
            "rescue_teams": 0,
            "food_units": 0,
        }

    average_distance = sum(
        item.get("distance_km", 0)
        for item in assignments
    ) / len(assignments)

    return {
        "response_time": max(
            5,
            round(average_distance * 5),
        ),

        "ambulances": len(
            set(
                item.get("ambulance_id")
                for item in assignments
            )
        ),
        "rescue_teams": len(assignments),
        "food_units": len(assignments) * 20,
    }

def convert_backend_output_to_frontend_metrics(
    backend_output,
    severity,
    affected_population,
    available_ambulances,
    available_rescue_teams,
    available_food_units,
):
    """
    Convert q_rescue backend allocation output into the format
    expected by the existing Streamlit dashboard.
    """
    greedy = backend_output["solvers"]["classical-greedy"]

    classical_metrics = solver_to_dashboard_metrics(
        backend_output["solvers"]["classical-greedy"]
    )

    qaoa_metrics = solver_to_dashboard_metrics(
        backend_output["solvers"]["qiskit-qaoa"]
    )

    assignments = greedy.get("assignments", [])

    if assignments:
        average_distance = (
            sum(item["distance_km"] for item in assignments)
            / len(assignments)
        )
    else:
        average_distance = 0

    # Existing dashboard metric compatibility
    response_time = max(
        5,
        int(average_distance * 5),
    )

    estimated_casualties = int(
        affected_population
        * (severity / 4)
        * 0.12
    )

    resources_needed = int(
        (affected_population / 1000)
        + (severity * 12)
    )

    optimisation_score = int(
        greedy.get("metrics", {})
        .get("coverage_percent", 0)
    )


    recommended_ambulances = max(
        available_ambulances,
        severity * 5,
    )

    recommended_rescue_teams = max(
        available_rescue_teams,
        severity * 3,
    )

    recommended_food_units = max(
        available_food_units,
        affected_population // 300,
    )

    # Risk distribution
    critical_risk = min(
        55,
        severity * 12,
    )

    high_risk = min(
        35,
        severity * 8,
    )

    medium_risk = max(
        10,
        30 - severity * 3,
    )

    low_risk = max(
        0,
        100
        - critical_risk
        - high_risk
        - medium_risk,
    )

    return {
        "estimated_casualties": estimated_casualties,
        "response_time": response_time,
        "resources_needed": resources_needed,
        "optimisation_score": optimisation_score,
        "recommended_ambulances": recommended_ambulances,
        "recommended_rescue_teams": recommended_rescue_teams,
        "recommended_food_units": recommended_food_units,
        "critical_risk": critical_risk,
        "high_risk": high_risk,
        "medium_risk": medium_risk,
        "low_risk": low_risk,

        "allocation_output": backend_output,

        # Solver outputs for comparison page
        "classical_greedy": backend_output["solvers"]["classical-greedy"],
        "qaoa_optimised": backend_output["solvers"]["qiskit-qaoa"],

        # Converted solver metrics for comparison charts
        "classical_metrics": classical_metrics,
        "qaoa_metrics": qaoa_metrics,
    }