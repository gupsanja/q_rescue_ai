import json
from pathlib import Path


from q_rescue.simulation.exporters import (
    export_flood_observations_csv,
    export_hydro_enriched_scenario,
    export_scenario_json,
)
from q_rescue.simulation.scenarios import generate_flood_scenario

def test_export_hydro_enriched_scenario(tmp_path: Path):
    # Setup
    scenario = generate_flood_scenario(seed=42)
    out_file = tmp_path / "hydro_enriched_scenario.json"
    
    # Act
    export_hydro_enriched_scenario(scenario, out_file, {})
    
    # Assert
    assert out_file.exists()
    with out_file.open() as f:
        data = json.load(f)
        
    assert "scenario_id" in data
    assert "incidents" in data
    assert len(data["incidents"]) == len(scenario.incidents)
    
    # Check that hydro features were included
    first_incident = data["incidents"][0]
    assert "hydro_features" in first_incident
    assert "rainfall_24h_mm" in first_incident["hydro_features"]
    assert "ai_prediction" in first_incident
    assert first_incident["ai_prediction"] is None

def test_export_flood_observations_csv(tmp_path: Path):
    # Setup
    scenario = generate_flood_scenario(seed=42)
    out_file = tmp_path / "flood_observations.csv"
    
    # Act
    export_flood_observations_csv(scenario, {}, out_file)
    
    # Assert
    assert out_file.exists()
    content = out_file.read_text().splitlines()
    
    # 1 header + N incidents
    assert len(content) == 1 + len(scenario.incidents)
    
    header = content[0].split(",")
    # 4 metadata columns + 14 feature columns = 18 total
    assert len(header) == 18
    assert header[0] == "observation_id"
    assert header[4] == "rainfall_24h_mm"

def test_export_scenario_json_includes_hydro_features(tmp_path: Path):
    # Setup
    scenario = generate_flood_scenario(seed=42)
    out_file = tmp_path / "scenario.json"
    
    # Act
    export_scenario_json(scenario, out_file)
    
    # Assert
    assert out_file.exists()
    with out_file.open() as f:
        data = json.load(f)
        
    first_incident = data["incidents"][0]
    # M2 Week 3 task: include hydro_features in main scenario export too
    assert "hydro_features" in first_incident
    assert first_incident["hydro_features"] is not None
    assert "rainfall_24h_mm" in first_incident["hydro_features"]
