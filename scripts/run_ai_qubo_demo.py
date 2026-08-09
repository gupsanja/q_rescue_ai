from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from q_rescue.quantum.comparison import ComparisonReport, SolverBenchmark, compare_solvers
from q_rescue.quantum.qubo import AmbulanceAllocationQuboBuilder
from q_rescue.simulation.scenarios import generate_flood_scenario


def main() -> None:
    args = _parse_args()
    run_ai_prediction_pipeline = _load_ai_pipeline()

    scenario = generate_flood_scenario(
        config={"simulation": {"ambulances": args.ambulances, "incidents": args.incidents}},
        seed=args.seed,
    )

    predictions, qubo_patch, dashboard_payload = run_ai_prediction_pipeline(
        scenario=scenario,
        hydro_params={},
        model_dir=args.model_dir,
        output_dir=args.output_dir,
    )

    base_builder = AmbulanceAllocationQuboBuilder(
        distance_weight=args.distance_weight,
        severity_weight=args.severity_weight,
        demand_weight=args.demand_weight,
        critical_priority=args.critical_priority,
    )
    patched_builder = base_builder.apply_ai_patch(qubo_patch)

    base_report = compare_solvers(
        scenario,
        builder=base_builder,
        run_exact=True,
        run_qaoa=args.run_qaoa,
    )
    patched_report = compare_solvers(
        scenario,
        builder=patched_builder,
        run_exact=True,
        run_qaoa=args.run_qaoa,
    )

    summary = _build_summary(
        scenario_name=scenario.name,
        predictions=predictions,
        qubo_patch=qubo_patch,
        dashboard_payload=dashboard_payload,
        base_report=base_report,
        patched_report=patched_report,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / "ai_qubo_before_after_summary.json"
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    _print_summary(summary, output_path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run an AI-patched QUBO before/after allocation demo"
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ambulances", type=int, default=3)
    parser.add_argument("--incidents", type=int, default=5)
    parser.add_argument("--distance-weight", type=float, default=1.0)
    parser.add_argument("--severity-weight", type=float, default=8.0)
    parser.add_argument("--demand-weight", type=float, default=8.0)
    parser.add_argument(
        "--critical-priority",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--run-qaoa",
        action="store_true",
        help="Also run local QAOA. Disabled by default for a fast deterministic demo.",
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("flood_xgboost_project/outputs"),
        help="Directory containing trained AI model artifacts.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/outputs/ai_qubo_demo"),
        help="Directory where AI artifacts and comparison summary are written.",
    )
    return parser.parse_args()


def _load_ai_pipeline() -> Any:
    try:
        from q_rescue.services.ai_integration import run_ai_prediction_pipeline
    except ModuleNotFoundError as exc:
        missing_package = exc.name or "AI dependency"
        raise SystemExit(
            f"Missing AI dependency: {missing_package}. "
            'Install the AI extras with: .venv/bin/python -m pip install -e ".[ai]"'
        ) from exc
    return run_ai_prediction_pipeline


def _build_summary(
    *,
    scenario_name: str,
    predictions: list[dict[str, Any]],
    qubo_patch: dict[str, Any],
    dashboard_payload: dict[str, Any],
    base_report: ComparisonReport,
    patched_report: ComparisonReport,
) -> dict[str, Any]:
    base_exact = _require_exact(base_report)
    patched_exact = _require_exact(patched_report)
    base_incidents = _assigned_incidents(base_exact)
    patched_incidents = _assigned_incidents(patched_exact)
    ai_high_risk_incidents = set(dashboard_payload["aggregate"]["high_risk_incident_ids"])
    base_ai_high_risk = base_incidents & ai_high_risk_incidents
    patched_ai_high_risk = patched_incidents & ai_high_risk_incidents

    return {
        "scenario_name": scenario_name,
        "binary_variables": patched_report.binary_variables,
        "ai_prediction_summary": {
            "model_version": qubo_patch["model_version"],
            "prediction_count": len(predictions),
            "high_risk_incident_ids": dashboard_payload["aggregate"]["high_risk_incident_ids"],
            "dominant_severity": dashboard_payload["aggregate"]["dominant_severity"],
            "mean_resource_demand": dashboard_payload["aggregate"]["mean_resource_demand"],
        },
        "qubo_patch": qubo_patch,
        "baseline_exact": _benchmark_to_dict(base_exact),
        "ai_patched_exact": _benchmark_to_dict(patched_exact),
        "changes": {
            "newly_selected_incidents": sorted(patched_incidents - base_incidents),
            "no_longer_selected_incidents": sorted(base_incidents - patched_incidents),
            "baseline_ai_high_risk_selected": sorted(base_ai_high_risk),
            "patched_ai_high_risk_selected": sorted(patched_ai_high_risk),
            "ai_high_risk_coverage_delta": _coverage_percent(
                len(patched_ai_high_risk), len(ai_high_risk_incidents)
            )
            - _coverage_percent(len(base_ai_high_risk), len(ai_high_risk_incidents)),
            "qubo_energy_delta": patched_exact.qubo_energy - base_exact.qubo_energy,
            "average_distance_delta": patched_exact.metrics["average_distance_km"]
            - base_exact.metrics["average_distance_km"],
            "critical_coverage_delta": patched_exact.metrics["critical_coverage_percent"]
            - base_exact.metrics["critical_coverage_percent"],
        },
    }


def _require_exact(report: ComparisonReport) -> SolverBenchmark:
    if report.exact is None:
        raise RuntimeError("Exact solver result is required for the before/after demo")
    return report.exact


def _assigned_incidents(benchmark: SolverBenchmark) -> set[str]:
    return {assignment.incident_id for assignment in benchmark.assignments}


def _benchmark_to_dict(benchmark: SolverBenchmark) -> dict[str, Any]:
    return {
        "solver_name": benchmark.solver_name,
        "feasible": benchmark.feasible,
        "qubo_energy": benchmark.qubo_energy,
        "runtime_seconds": benchmark.runtime_seconds,
        "metrics": benchmark.metrics,
        "assignments": [
            {
                "ambulance_id": assignment.ambulance_id,
                "incident_id": assignment.incident_id,
                "distance_km": assignment.distance,
            }
            for assignment in benchmark.assignments
        ],
    }


def _coverage_percent(selected_count: int, total_count: int) -> float:
    if total_count == 0:
        return 0.0
    return 100.0 * selected_count / total_count


def _print_summary(summary: dict[str, Any], output_path: Path) -> None:
    changes = summary["changes"]
    print(f"Scenario: {summary['scenario_name']}")
    print(f"Binary variables: {summary['binary_variables']}")
    print(f"Dominant AI severity: {summary['ai_prediction_summary']['dominant_severity']}")
    print(
        "High-risk incidents: "
        + ", ".join(summary["ai_prediction_summary"]["high_risk_incident_ids"])
    )
    print()
    print("Baseline exact assignments:")
    print(_format_assignments(summary["baseline_exact"]["assignments"]))
    print("AI-patched exact assignments:")
    print(_format_assignments(summary["ai_patched_exact"]["assignments"]))
    print()
    print(f"Newly selected incidents: {changes['newly_selected_incidents']}")
    print(f"No longer selected incidents: {changes['no_longer_selected_incidents']}")
    print(f"Baseline AI high-risk selected: {changes['baseline_ai_high_risk_selected']}")
    print(f"Patched AI high-risk selected: {changes['patched_ai_high_risk_selected']}")
    print(f"AI high-risk coverage delta: {changes['ai_high_risk_coverage_delta']:.1f}%")
    print(f"QUBO energy delta: {changes['qubo_energy_delta']:.6f}")
    print(f"Average distance delta: {changes['average_distance_delta']:.3f} km")
    print(f"Original-severity critical coverage delta: {changes['critical_coverage_delta']:.1f}%")
    print(f"Wrote {output_path}")


def _format_assignments(assignments: list[dict[str, Any]]) -> str:
    if not assignments:
        return "  none"
    return "\n".join(
        f"  {item['ambulance_id']} -> {item['incident_id']} ({item['distance_km']:.3f} km)"
        for item in assignments
    )


if __name__ == "__main__":
    main()
