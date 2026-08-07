"""
Generate a synthetic but realistic flood-event dataset.

Each row represents a flood-monitoring observation (e.g. a river gauge /
district reading during a storm event) with hydrological, meteorological,
and socio-geographic features. Two targets are derived from a shared
latent "flood risk" process so that severity and resource demand are
correlated (as they are in reality) but not identical:

  1. flood_severity      -> multi-class classification target
                             {Low, Moderate, High, Severe}
  2. resource_demand_units -> regression target (0-1000+), representing a
                             composite index of emergency resources needed
                             (personnel, boats, shelter capacity, pumps)
"""
import numpy as np
import pandas as pd
from pathlib import Path

RNG = np.random.default_rng(42)
N = 6000

OUT_DIR = Path(__file__).resolve().parents[1] / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def generate():
    # ---- Core meteorological / hydrological features ----
    rainfall_24h_mm = RNG.gamma(shape=2.0, scale=25, size=N)          # 0-250ish, right-skewed
    rainfall_72h_mm = rainfall_24h_mm * RNG.uniform(1.5, 3.2, N) + RNG.normal(0, 10, N)
    rainfall_72h_mm = np.clip(rainfall_72h_mm, 0, None)

    river_level_baseline_m = RNG.normal(3.0, 0.6, N)
    river_level_m = river_level_baseline_m + 0.018 * rainfall_72h_mm + RNG.normal(0, 0.3, N)
    river_level_m = np.clip(river_level_m, 0.5, None)

    river_level_change_rate = 0.012 * rainfall_24h_mm + RNG.normal(0, 0.15, N)

    soil_saturation_pct = np.clip(
        30 + 0.35 * rainfall_72h_mm + RNG.normal(0, 8, N), 0, 100
    )

    upstream_dam_release_m3s = np.clip(
        RNG.gamma(shape=2.0, scale=40, size=N) + 0.5 * rainfall_72h_mm, 0, None
    )

    temperature_c = RNG.normal(18, 7, N)
    wind_speed_kmh = np.clip(RNG.gamma(2.2, 12, N), 0, None)

    # ---- Geographic / socio-economic features ----
    elevation_m = np.clip(RNG.gamma(2.0, 40, N), 0, None)              # low elevation = higher risk
    distance_to_river_km = np.clip(RNG.exponential(2.5, N), 0.05, None)
    drainage_capacity_index = np.clip(RNG.beta(2.5, 2.0, N), 0, 1)     # 0=poor,1=excellent
    urbanization_pct = np.clip(RNG.beta(2.0, 2.0, N) * 100, 0, 100)
    population_density_per_km2 = np.clip(
        RNG.gamma(2.0, 800, N) * (0.4 + urbanization_pct / 100), 5, None
    )
    previous_flood_history = RNG.binomial(1, 0.3, N)

    # ---- Latent flood risk score (nonlinear combination + interactions) ----
    risk = (
        0.028 * rainfall_24h_mm
        + 0.014 * rainfall_72h_mm
        + 1.10 * river_level_m
        + 9.0 * river_level_change_rate
        + 0.022 * soil_saturation_pct
        + 0.006 * upstream_dam_release_m3s
        - 0.010 * elevation_m
        - 0.55 * distance_to_river_km
        - 2.6 * drainage_capacity_index
        + 0.9 * previous_flood_history
        + 0.010 * wind_speed_kmh
        # interaction: saturated soil + high rainfall compounds risk
        + 0.00035 * rainfall_72h_mm * soil_saturation_pct
        # interaction: poor drainage amplifies rainfall impact (nonlinear -> favors tree models)
        + 0.02 * rainfall_24h_mm * (1 - drainage_capacity_index)
        # low elevation near river is much worse
        - 0.15 * elevation_m / (distance_to_river_km + 0.5)
    )
    risk += RNG.normal(0, 1.2, N)  # observation noise

    # ---- Severity classes from risk quantile thresholds ----
    q = np.quantile(risk, [0.40, 0.72, 0.92])
    severity_codes = np.digitize(risk, q)  # 0=Low,1=Moderate,2=High,3=Severe
    severity_labels = np.array(["Low", "Moderate", "High", "Severe"])[severity_codes]

    # ---- Resource demand (regression target) ----
    # driven by severity/risk plus exposure (population, urbanization),
    # with its own nonlinear interaction and noise so it's related to,
    # but not a deterministic function of, severity class.
    base_demand = 40 + 55 * np.clip(risk - risk.min(), 0, None)
    exposure_multiplier = 1 + 0.9 * (population_density_per_km2 / population_density_per_km2.max())
    urbanization_effect = 1 + 0.006 * urbanization_pct
    resource_demand_units = (
        base_demand * exposure_multiplier * urbanization_effect
        + 0.08 * population_density_per_km2 ** 0.5
        + RNG.normal(0, 25, N)
    )
    resource_demand_units = np.clip(resource_demand_units, 5, None)

    df = pd.DataFrame(
        {
            "rainfall_24h_mm": rainfall_24h_mm,
            "rainfall_72h_mm": rainfall_72h_mm,
            "river_level_m": river_level_m,
            "river_level_change_rate": river_level_change_rate,
            "soil_saturation_pct": soil_saturation_pct,
            "upstream_dam_release_m3s": upstream_dam_release_m3s,
            "temperature_c": temperature_c,
            "wind_speed_kmh": wind_speed_kmh,
            "elevation_m": elevation_m,
            "distance_to_river_km": distance_to_river_km,
            "drainage_capacity_index": drainage_capacity_index,
            "urbanization_pct": urbanization_pct,
            "population_density_per_km2": population_density_per_km2,
            "previous_flood_history": previous_flood_history,
            "flood_severity": severity_labels,
            "resource_demand_units": resource_demand_units,
        }
    )

    return df


if __name__ == "__main__":
    df = generate()
    out_path = OUT_DIR / "flood_dataset.csv"
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} rows to {out_path}")
    print(df["flood_severity"].value_counts(normalize=True).round(3))
    print(df.describe().T[["mean", "std", "min", "max"]].round(2))
