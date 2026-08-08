import os
from pathlib import Path
from q_rescue.simulation.scenarios import generate_flood_scenario, generate_generic_scenario, generate_industrial_scenario, generate_city_wide_scenario
from q_rescue.simulation.exporters import export_hydro_enriched_scenario, export_flood_observations_csv

def main():
    out_dir = Path("data/outputs")
    
    for seed in range(42, 53):
        print(f"Generating flood scenario for seed {seed}...")
        scenario = generate_flood_scenario(seed=seed)
        scenario_id = scenario.name.lower().replace(" ", "_")
        
        scenario_dir = out_dir / scenario_id
        scenario_dir.mkdir(parents=True, exist_ok=True)
        
        export_hydro_enriched_scenario(scenario, scenario_dir / "hydro_enriched_scenario.json", {})
        export_flood_observations_csv(scenario, {}, scenario_dir / "flood_observations.csv")
        
    print("Validating no regressions in other generators...")
    _ = generate_generic_scenario(seed=42)
    _ = generate_industrial_scenario(seed=42)
    _ = generate_city_wide_scenario(seed=42)
    print("Done! Datasets successfully generated.")

if __name__ == "__main__":
    main()
