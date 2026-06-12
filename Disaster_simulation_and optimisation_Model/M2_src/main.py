import tomllib
from pathlib import Path

from q_rescue.domain.models import DisasterCategory
from q_rescue.simulation.scenarios import generate_scenario_by_category
from q_rescue.simulation.cost_matrix import build_cost_matrix
from q_rescue.simulation.exporters import export_all

# Project root is three levels up: M2_src/ -> Disaster_simulation_.../ -> q_rescue_ai/
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def main() -> None:
    # Load configuration
    config_path = _PROJECT_ROOT / "configs" / "default.toml"
    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    # 1. Parse category
    category_str = config.get("simulation", {}).get("category", "generic")
    try:
        category = DisasterCategory(category_str)
    except ValueError:
        print(f"Warning: Unknown category '{category_str}', falling back to GENERIC.")
        category = DisasterCategory.GENERIC

    seed = int(config.get("simulation", {}).get("seed", 42))

    # 2. Generate scenario
    print(f"Generating {category.value} scenario (seed={seed})...")
    scenario = generate_scenario_by_category(category, config, seed=seed)
    print(f"Generated {len(scenario.ambulances)} ambulances, "
          f"{len(scenario.incidents)} incidents.")

    # 3. Build Cost Matrix
    opt_config = config.get("optimisation", {})
    dist_w = float(opt_config.get("distance_weight", 1.0))
    sev_w = float(opt_config.get("severity_weight", 8.0))

    print("Building cost matrix (Haversine distance)...")
    cost_matrix = build_cost_matrix(
        scenario,
        distance_weight=dist_w,
        severity_weight=sev_w,
    )

    # 4. Export Outputs
    export_config = config.get("export", {})
    out_dir_str = str(export_config.get("output_dir", "data/outputs"))
    formats = list(export_config.get("formats", ["json", "csv"]))

    out_dir = _PROJECT_ROOT / out_dir_str
    print(f"Exporting data to {out_dir}...")

    generated = export_all(scenario, cost_matrix, out_dir, formats=formats)
    for name, path in generated.items():
        print(f"  - {name}: {path.relative_to(_PROJECT_ROOT)}")

    print("Done.")


if __name__ == "__main__":
    main()