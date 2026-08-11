"""Shared application workflow connecting simulation, AI, allocation, metrics and dashboard.

This module is the integration boundary. Existing domain, simulation, classical,
quantum and metrics implementations remain independently usable; this service
only composes them through stable JSON-compatible payloads.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from q_rescue.ai.validation import EXPECTED_FEATURES
from q_rescue.api.prediction_api import PredictionAPI
from q_rescue.api.contracts import ContractValidationError, validate_qubo_patch_contract
from q_rescue.classical.allocator import GreedyAllocator, OptimalAssignmentAllocator
from q_rescue.simulation.generator import DisasterScenario
from q_rescue.metrics.evaluator import calculate_metrics
from q_rescue.quantum.optimizer import QuantumAllocator
from q_rescue.quantum.qaoa_solver import ExactQuboSolver
from q_rescue.quantum.qubo import AmbulanceAllocationQuboBuilder
from q_rescue.simulation.distance_matrix import (
    SeverityMapping,
    build_distance_matrix,
    build_severity_mapping,
)


def build_prediction_request(
    scenario: DisasterScenario,
    *,
    model_dir: Path,
    timestamp_utc: str | None = None,
) -> dict[str, Any]:
    """Build the canonical AI request from a simulation scenario.

    The AI model currently targets flood observations. Missing hydrological
    features are rejected rather than invented.
    """
    scenario_id = scenario_id_for(scenario)
    timestamp = timestamp_utc or datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    observations: list[dict[str, Any]] = []

    for incident in scenario.incidents:
        features = getattr(incident, "hydro_features", None)
        if not isinstance(features, dict):
            raise ContractValidationError(
                f"Incident {incident.id} has no hydro_features; "
                "the flood AI model cannot infer from incomplete input.",
                code="MISSING_HYDRO_FEATURES",
            )
        missing = [name for name in EXPECTED_FEATURES if name not in features]
        if missing:
            raise ContractValidationError(
                f"Incident {incident.id} is missing AI features: {missing}",
                code="MISSING_FEATURES",
            )
        observations.append(
            {
                "observation_id": f"OBS_{scenario_id}_{incident.id}",
                "incident_id": incident.id,
                "scenario_id": scenario_id,
                "timestamp_utc": timestamp,
                "lat": round(incident.location.x, 6),
                "lon": round(incident.location.y, 6),
                **{name: features[name] for name in EXPECTED_FEATURES},
            }
        )

    return {
        "api_version": "1.0",
        "scenario_id": scenario_id,
        "observations": observations,
        "model_dir": str(model_dir),
    }


def run_application_workflow(
    scenario: DisasterScenario,
    *,
    model_dir: Path | None = None,
    run_ai: bool = True,
    run_quantum: bool = True,
    quantum_variable_limit: int = 24,
) -> dict[str, Any]:
    """Run the complete application workflow and return one dashboard contract.

    Flow:
        Simulation -> AI Prediction (optional) -> classical baseline +
        quantum allocation -> common metrics -> dashboard payload.

    The classical baseline is always executed. Quantum exact enumeration is
    automatically skipped above its safe variable limit. AI is explicitly
    marked ``not_applicable`` for scenarios without flood features.
    """
    distance_matrix = build_distance_matrix(scenario)
    severity_mapping = build_severity_mapping(scenario)

    # Classical baselines: keep both the simple greedy reference and the
    # min-cost-flow allocation so the assessment can distinguish a heuristic
    # baseline from the stronger classical benchmark.
    greedy = GreedyAllocator().solve(
        scenario.ambulances, scenario.incidents, distance_matrix, severity_mapping
    )
    classical = OptimalAssignmentAllocator().solve(
        scenario.ambulances, scenario.incidents, distance_matrix, severity_mapping
    )

    ai_result: dict[str, Any]
    ai_patch: dict[str, Any] | None = None
    if not run_ai:
        ai_result = {"status": "disabled", "reason": "AI prediction disabled by request"}
    elif model_dir is None:
        ai_result = {"status": "not_configured", "reason": "No AI model directory configured"}
    elif scenario.category.value != "flood":
        ai_result = {
            "status": "not_applicable",
            "reason": "The configured prediction model is a flood-risk model",
        }
    else:
        try:
            ai_response = PredictionAPI().predict(
                build_prediction_request(scenario, model_dir=model_dir)
            )
            ai_result = {
                "status": "ok",
                "predictions": ai_response["predictions"],
                "qubo_patch": ai_response["qubo_patch"],
                "dashboard_payload": ai_response["dashboard_payload"],
                "validation": ai_response["validation"],
            }
            ai_patch = ai_response["qubo_patch"]
        except ContractValidationError as exc:
            ai_result = {
                "status": "validation_error",
                "error_code": exc.code,
                "reason": str(exc),
            }
        except (FileNotFoundError, ImportError, OSError, ValueError) as exc:
            # Do not silently substitute a heuristic for the AI layer. The
            # dashboard receives an explicit unavailable state instead.
            ai_result = {
                "status": "unavailable",
                "reason": str(exc),
            }

    quantum_payload: dict[str, Any]
    if not run_quantum:
        quantum_payload = {"status": "disabled", "solver_name": "quantum"}
    elif len(scenario.ambulances) * len(scenario.incidents) > quantum_variable_limit:
        quantum_payload = {
            "status": "skipped",
            "solver_name": "exact-enumeration",
            "reason": (
                f"exact enumeration skipped because "
                f"{len(scenario.ambulances) * len(scenario.incidents)} binary variables "
                f"exceed the configured limit of {quantum_variable_limit}"
            ),
        }
    else:
        builder = AmbulanceAllocationQuboBuilder(critical_priority=True)
        if ai_patch:
            validate_qubo_patch_contract(
                ai_patch,
                scenario_id=ai_patch["scenario_id"],
                incident_ids=[incident.id for incident in scenario.incidents],
            )
            builder = builder.apply_ai_patch(ai_patch)
        quantum_result = QuantumAllocator(
            builder=builder,
            solver=ExactQuboSolver(),
        ).solve(
            scenario.ambulances,
            scenario.incidents,
            distance_matrix,
            severity_mapping,
        )
        quantum_payload = _result_payload(quantum_result, scenario)

    dashboard_payload = {
        "contract_version": "1.0",
        "generated_at_utc": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scenario": _scenario_payload(scenario),
        "prediction": ai_result,
        "allocation": {
            "classical_baseline": _result_payload(greedy, scenario),
            "classical_optimal": _result_payload(classical, scenario),
            "quantum": quantum_payload,
        },
        "metrics": {
            "classical_baseline": calculate_metrics(greedy, scenario.incidents),
            "classical_optimal": calculate_metrics(classical, scenario.incidents),
            "quantum": (
                calculate_metrics(quantum_result, scenario.incidents)
                if "quantum_result" in locals()
                else None
            ),
        },
        "integration": {
            "distance_matrix": distance_matrix.to_dict(),
            "severity_weights": severity_mapping,
            "ai_patch_applied_to_quantum": ai_patch is not None,
            "human_oversight_required": True,
            "automated_decision_status": "recommendation_only",
        },
    }
    return dashboard_payload


def scenario_id_for(scenario: DisasterScenario) -> str:
    """Return the canonical scenario identifier shared across contracts."""
    return scenario.name.lower().replace(" ", "_")


def _result_payload(result: Any, scenario: DisasterScenario) -> dict[str, Any]:
    return {
        "status": "ok",
        "solver_name": result.solver_name,
        "objective_value": result.objective_value,
        "feasible": result.feasible,
        "metrics": calculate_metrics(result, scenario.incidents),
        "assignments": [
            {
                "ambulance_id": item.ambulance_id,
                "incident_id": item.incident_id,
                "distance_km": item.distance,
                "hospital_id": item.hospital_id,
            }
            for item in result.assignments
        ],
    }


def _scenario_payload(scenario: DisasterScenario) -> dict[str, Any]:
    return {
        "id": scenario_id_for(scenario),
        "name": scenario.name,
        "category": scenario.category.value,
        "counts": {
            "ambulances": len(scenario.ambulances),
            "incidents": len(scenario.incidents),
            "hospitals": len(scenario.hospitals),
        },
        "incidents": [
            {
                "id": incident.id,
                "lat": round(incident.location.x, 6),
                "lon": round(incident.location.y, 6),
                "severity": incident.severity.name,
                "severity_weight": incident.severity.absolute_weight(),
            }
            for incident in scenario.incidents
        ],
    }


__all__ = ["build_prediction_request", "run_application_workflow", "scenario_id_for"]
