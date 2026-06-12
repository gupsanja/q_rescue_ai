import json
import csv
from pathlib import Path

from q_rescue.simulation.scenarios import generate_generic_scenario
from q_rescue.simulation.cost_matrix import build_cost_matrix
from q_rescue.simulation.exporters import export_all


def test_export_all_generates_files(tmp_path: Path):
    scenario = generate_generic_scenario()
    cost_matrix = build_cost_matrix(scenario)
    
    generated = export_all(scenario, cost_matrix, tmp_path)
    
    assert "scenario_json" in generated
    assert "cost_matrix_json" in generated
    assert "ambulances_csv" in generated
    assert "incidents_csv" in generated
    assert "hospitals_csv" in generated
    assert "cost_matrix_csv" in generated
    
    for path in generated.values():
        assert path.exists()
        assert path.stat().st_size > 0


def test_scenario_json_structure(tmp_path: Path):
    scenario = generate_generic_scenario()
    cost_matrix = build_cost_matrix(scenario)
    
    generated = export_all(scenario, cost_matrix, tmp_path, formats=["json"])
    
    with open(generated["scenario_json"]) as f:
        data = json.load(f)
        
    assert data["name"] == scenario.name
    assert len(data["ambulances"]) == len(scenario.ambulances)
    assert len(data["incidents"]) == len(scenario.incidents)
    assert len(data["hospitals"]) == len(scenario.hospitals)
    
    # Check severity weight is exported correctly
    assert "severity_weight" in data["incidents"][0]


def test_cost_matrix_csv_structure(tmp_path: Path):
    scenario = generate_generic_scenario()
    cost_matrix = build_cost_matrix(scenario)
    
    generated = export_all(scenario, cost_matrix, tmp_path, formats=["csv"])
    
    with open(generated["cost_matrix_csv"], newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
        
    header = rows[0]
    assert header[0] == "ambulance_id"
    assert header[1:] == cost_matrix.incident_ids
    
    first_data_row = rows[1]
    assert first_data_row[0] == cost_matrix.ambulance_ids[0]
    assert len(first_data_row) == len(header)
