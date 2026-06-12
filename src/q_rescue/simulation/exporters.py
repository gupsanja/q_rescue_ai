"""Export module for simulation scenarios and cost matrices.

Provides functions to serialise ``DisasterScenario`` and ``CostMatrix``
objects to JSON and CSV formats for use by the frontend and downstream
solvers.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from q_rescue.simulation.cost_matrix import CostMatrix
from q_rescue.simulation.generator import DisasterScenario


# ---------------------------------------------------------------------------
# JSON Exporters
# ---------------------------------------------------------------------------


def export_scenario_json(scenario: DisasterScenario, path: Path) -> None:
    """Export the entire scenario to a single JSON file."""
    data = {
        "name": scenario.name,
        "category": scenario.category.value,
        "ambulances": [
            {
                "id": a.id,
                "lat": round(a.location.x, 6),
                "lon": round(a.location.y, 6),
                "status": a.status,
            }
            for a in scenario.ambulances
        ],
        "incidents": [
            {
                "id": i.id,
                "lat": round(i.location.x, 6),
                "lon": round(i.location.y, 6),
                "severity_level": i.severity.name,
                "severity_weight": i.severity.absolute_weight(),
            }
            for i in scenario.incidents
        ],
        "hospitals": [
            {
                "id": h.id,
                "name": h.name,
                "lat": round(h.location.x, 6),
                "lon": round(h.location.y, 6),
                "capacity": h.capacity,
                "available_beds": h.available_beds,
            }
            for h in scenario.hospitals
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def export_cost_matrix_json(cost_matrix: CostMatrix, path: Path) -> None:
    """Export the nested dict cost matrix to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(cost_matrix.to_dict(), f, indent=4)


# ---------------------------------------------------------------------------
# CSV Exporters
# ---------------------------------------------------------------------------


def export_scenario_csv(scenario: DisasterScenario, output_dir: Path) -> None:
    """Export the scenario into separate CSV files (ambulances, incidents, hospitals)."""
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_csv(
        output_dir / "ambulances.csv",
        headers=["id", "lat", "lon", "status"],
        rows=[
            [a.id, round(a.location.x, 6), round(a.location.y, 6), a.status]
            for a in scenario.ambulances
        ],
    )

    _write_csv(
        output_dir / "incidents.csv",
        headers=["id", "lat", "lon", "severity_level", "severity_weight", "category"],
        rows=[
            [
                i.id,
                round(i.location.x, 6),
                round(i.location.y, 6),
                i.severity.name,
                i.severity.absolute_weight(),
                i.category.value,
            ]
            for i in scenario.incidents
        ],
    )

    _write_csv(
        output_dir / "hospitals.csv",
        headers=["id", "name", "lat", "lon", "capacity", "available_beds"],
        rows=[
            [
                h.id,
                h.name,
                round(h.location.x, 6),
                round(h.location.y, 6),
                h.capacity,
                h.available_beds,
            ]
            for h in scenario.hospitals
        ],
    )


def export_cost_matrix_csv(cost_matrix: CostMatrix, path: Path) -> None:
    """Export the cost matrix to CSV (rows = ambulances, cols = incidents)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        # Header row
        writer.writerow(["ambulance_id"] + cost_matrix.incident_ids)
        # Data rows
        for a_id in cost_matrix.ambulance_ids:
            row = [a_id]
            for i_id in cost_matrix.incident_ids:
                row.append(cost_matrix.matrix[a_id][i_id])
            writer.writerow(row)


def _write_csv(path: Path, headers: list[str], rows: list[list[Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# One-shot Export
# ---------------------------------------------------------------------------


def export_all(
    scenario: DisasterScenario,
    cost_matrix: CostMatrix,
    output_dir: Path,
    formats: list[str] | None = None,
) -> dict[str, Path]:
    """Generate all requested exports in a single call.

    Args:
        scenario: The simulated scenario.
        cost_matrix: The computed cost matrix.
        output_dir: Target directory for all output files.
        formats: List containing "json", "csv", or both. Defaults to both.

    Returns:
        A dict mapping descriptive names to the generated file paths.
    """
    if formats is None:
        formats = ["json", "csv"]

    output_dir.mkdir(parents=True, exist_ok=True)
    generated: dict[str, Path] = {}

    if "json" in formats:
        p_scen = output_dir / "scenario.json"
        p_cost = output_dir / "cost_matrix.json"
        export_scenario_json(scenario, p_scen)
        export_cost_matrix_json(cost_matrix, p_cost)
        generated["scenario_json"] = p_scen
        generated["cost_matrix_json"] = p_cost

    if "csv" in formats:
        export_scenario_csv(scenario, output_dir)
        p_cost_csv = output_dir / "cost_matrix.csv"
        export_cost_matrix_csv(cost_matrix, p_cost_csv)
        generated["ambulances_csv"] = output_dir / "ambulances.csv"
        generated["incidents_csv"] = output_dir / "incidents.csv"
        generated["hospitals_csv"] = output_dir / "hospitals.csv"
        generated["cost_matrix_csv"] = p_cost_csv

    return generated
