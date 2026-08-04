"""Disaster scenario generators for Q-Rescue AI.

Each generator produces a ``DisasterScenario`` tailored to a specific
Sheffield disaster archetype. All generators are deterministic when given
the same ``seed``.

Usage::

    from q_rescue.simulation.scenarios import generate_scenario_by_category
    from q_rescue.domain.models import DisasterCategory

    scenario = generate_scenario_by_category(
        DisasterCategory.FLOOD, config={"simulation": {"ambulances": 5}}
    )

All configuration is read from the ``config`` dict (matching the structure
of ``configs/default.toml``). Missing keys fall back to safe defaults.
"""

from __future__ import annotations

from random import Random

from q_rescue.domain.models import (
    Ambulance,
    DisasterCategory,
    Hospital,
    Incident,
    Severity,
)
from q_rescue.simulation.generator import DisasterScenario
from q_rescue.simulation.sheffield import (
    FLOOD_ZONES,
    INDUSTRIAL_ZONES,
    SHEFFIELD_HOSPITALS,
    clustered_location,
    random_sheffield_location,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _cfg(config: dict, *keys: str, default: object) -> object:
    """Safely traverse nested config dict and return a fallback if missing."""
    node: object = config
    for key in keys:
        if not isinstance(node, dict):
            return default
        node = node.get(key, default)
    return node


def _generate_ambulances(rng: Random, count: int) -> list[Ambulance]:
    return [
        Ambulance(id=f"A{i + 1}", location=random_sheffield_location(rng)) for i in range(count)
    ]


def _apply_capacity_multiplier(hospitals: list[Hospital], multiplier: float) -> list[Hospital]:
    """Return a new list of hospitals with available_beds scaled by multiplier."""
    return [
        Hospital(
            id=h.id,
            name=h.name,
            location=h.location,
            capacity=h.capacity,
            available_beds=max(0, int(h.available_beds * multiplier)),
        )
        for h in hospitals
    ]


def _generate_hydro_features(rng: Random, location: object, rainfall_24h: float) -> dict[str, float | int]:
    """Generate 14 hydrological/geographic features for a flood incident."""
    rainfall_72h = rainfall_24h + rng.uniform(20.0, 150.0)
    river_level = rng.uniform(0.5, 8.0)
    river_rate = rng.uniform(-0.5, 1.5)
    soil_sat = rng.uniform(40.0, 100.0)
    upstream = rng.uniform(0.0, 300.0)
    temp = rng.uniform(-5.0, 25.0)
    wind = rng.uniform(0.0, 80.0)
    
    elevation = rng.uniform(10.0, 300.0)
    dist_river = rng.uniform(0.05, 5.0)
    drainage = rng.uniform(0.0, 1.0)
    urban = rng.uniform(10.0, 100.0)
    pop_density = rng.uniform(100.0, 5000.0)
    history = rng.choice([0, 1])

    return {
        "rainfall_24h_mm": round(rainfall_24h, 1),
        "rainfall_72h_mm": round(rainfall_72h, 1),
        "river_level_m": round(river_level, 2),
        "river_level_change_rate": round(river_rate, 2),
        "soil_saturation_pct": round(soil_sat, 1),
        "upstream_dam_release_m3s": round(upstream, 1),
        "temperature_c": round(temp, 1),
        "wind_speed_kmh": round(wind, 1),
        "elevation_m": round(elevation, 1),
        "distance_to_river_km": round(dist_river, 2),
        "drainage_capacity_index": round(drainage, 2),
        "urbanization_pct": round(urban, 1),
        "population_density_per_km2": round(pop_density, 1),
        "previous_flood_history": history,
    }


# ---------------------------------------------------------------------------
# Scenario generators
# ---------------------------------------------------------------------------


def generate_generic_scenario(
    config: dict | None = None,
    seed: int = 42,
) -> DisasterScenario:
    """Random uniform incidents distributed across Sheffield.

    Severity distribution: equal probability for all four levels.
    """
    config = config or {}
    rng = Random(seed)
    num_ambulances = int(_cfg(config, "simulation", "ambulances", default=3))  # type: ignore[arg-type]
    num_incidents = int(_cfg(config, "simulation", "incidents", default=5))  # type: ignore[arg-type]

    ambulances = _generate_ambulances(rng, num_ambulances)
    incidents = [
        Incident(
            id=f"I{i + 1}",
            location=random_sheffield_location(rng),
            severity=Severity(rng.randint(1, 4)),
            category=DisasterCategory.GENERIC,
        )
        for i in range(num_incidents)
    ]
    return DisasterScenario(
        name=f"Generic Scenario (seed={seed})",
        ambulances=ambulances,
        incidents=incidents,
        hospitals=list(SHEFFIELD_HOSPITALS),
        category=DisasterCategory.GENERIC,
    )


def generate_flood_scenario(
    config: dict | None = None,
    seed: int = 42,
) -> DisasterScenario:
    """Sheffield flood response scenario.

    Characteristics:
    - 70% of incidents clustered within 1 km of Don/Sheaf flood zone centroids.
    - Elevated severity: 60% of incidents are High or Critical.
    - Hospital capacity reduced to 70% (flood damage + surge).
    """
    config = config or {}
    rng = Random(seed)
    num_ambulances = int(_cfg(config, "simulation", "ambulances", default=3))  # type: ignore[arg-type]
    num_incidents = int(_cfg(config, "simulation", "incidents", default=5))  # type: ignore[arg-type]
    cluster_radius = float(_cfg(config, "simulation", "cluster_radius_km", default=1.0))  # type: ignore[arg-type]

    ambulances = _generate_ambulances(rng, num_ambulances)

    # Severity weights: 10% Low, 30% Medium, 35% High, 25% Critical
    severity_pool = (
        [Severity.LOW] * 10
        + [Severity.MEDIUM] * 30
        + [Severity.HIGH] * 35
        + [Severity.CRITICAL] * 25
    )

    rainfall_24h = float(_cfg(config, "simulation", "rainfall_24h_mm", default=rng.uniform(50.0, 150.0)))

    incidents = []
    for i in range(num_incidents):  # num_incidents is int after cast above
        if rng.random() < 0.70:
            # Clustered near a flood zone
            zone = rng.choice(FLOOD_ZONES)
            location = clustered_location(rng, zone, radius_km=cluster_radius)
        else:
            location = random_sheffield_location(rng)

        incident = Incident(
            id=f"I{i + 1}",
            location=location,
            severity=rng.choice(severity_pool),
            category=DisasterCategory.FLOOD,
        )
        
        # Attach generated hydro features directly to the frozen Incident dataclass instance
        hydro_features = _generate_hydro_features(rng, location, rainfall_24h)
        object.__setattr__(incident, "hydro_features", hydro_features)
        
        incidents.append(incident)

    hospitals = _apply_capacity_multiplier(SHEFFIELD_HOSPITALS, 0.70)

    return DisasterScenario(
        name=f"Sheffield Flood Response (seed={seed})",
        ambulances=ambulances,
        incidents=incidents,
        hospitals=hospitals,
        category=DisasterCategory.FLOOD,
    )


def generate_industrial_scenario(
    config: dict | None = None,
    seed: int = 42,
) -> DisasterScenario:
    """Industrial/chemical accident in Sheffield's east end.

    Characteristics:
    - 80% of incidents clustered within 0.5 km of Tinsley/Attercliffe zones.
    - 50% Critical severity (chemical/explosion hazard).
    - Nearest hospital at 90% capacity (trauma surge).
    """
    config = config or {}
    rng = Random(seed)
    num_ambulances = int(_cfg(config, "simulation", "ambulances", default=3))  # type: ignore[arg-type]
    num_incidents = int(_cfg(config, "simulation", "incidents", default=5))  # type: ignore[arg-type]
    cluster_radius = float(_cfg(config, "simulation", "cluster_radius_km", default=0.5))  # type: ignore[arg-type]

    ambulances = _generate_ambulances(rng, num_ambulances)

    # Severity weights: 5% Low, 15% Medium, 30% High, 50% Critical
    severity_pool = (
        [Severity.LOW] * 5
        + [Severity.MEDIUM] * 15
        + [Severity.HIGH] * 30
        + [Severity.CRITICAL] * 50
    )

    incidents = []
    for i in range(num_incidents):
        if rng.random() < 0.80:
            zone = rng.choice(INDUSTRIAL_ZONES)
            location = clustered_location(rng, zone, radius_km=cluster_radius)
        else:
            location = random_sheffield_location(rng)

        incidents.append(
            Incident(
                id=f"I{i + 1}",
                location=location,
                severity=rng.choice(severity_pool),
                category=DisasterCategory.INDUSTRIAL_ACCIDENT,
            )
        )

    # Set nearest hospital (Northern General) to 90% capacity
    hospitals = []
    for h in SHEFFIELD_HOSPITALS:
        if h.id == "H1":  # Northern General — closest to Tinsley
            hospitals.append(
                Hospital(
                    id=h.id,
                    name=h.name,
                    location=h.location,
                    capacity=h.capacity,
                    available_beds=max(0, int(h.available_beds * 0.10)),
                )
            )
        else:
            hospitals.append(h)

    return DisasterScenario(
        name=f"Sheffield Industrial Accident (seed={seed})",
        ambulances=ambulances,
        incidents=incidents,
        hospitals=hospitals,
        category=DisasterCategory.INDUSTRIAL_ACCIDENT,
    )


def generate_city_wide_scenario(
    config: dict | None = None,
    seed: int = 42,
) -> DisasterScenario:
    """City-wide emergency across all of Sheffield.

    Characteristics:
    - Double the default incident count to model high resource competition.
    - Equal severity distribution (25% each level) for mixed casualty types.
    - All hospitals operating at normal capacity.
    - Ambulances distributed across the whole city.
    """
    config = config or {}
    rng = Random(seed)
    num_ambulances = int(_cfg(config, "simulation", "ambulances", default=3))  # type: ignore[arg-type]
    # City-wide scenarios use double the configured incident count
    num_incidents = int(_cfg(config, "simulation", "incidents", default=5)) * 2  # type: ignore[arg-type]

    ambulances = _generate_ambulances(rng, num_ambulances)
    incidents = [
        Incident(
            id=f"I{i + 1}",
            location=random_sheffield_location(rng),
            severity=Severity(rng.randint(1, 4)),
            category=DisasterCategory.CITY_WIDE_EMERGENCY,
        )
        for i in range(num_incidents)
    ]

    return DisasterScenario(
        name=f"Sheffield City-Wide Emergency (seed={seed})",
        ambulances=ambulances,
        incidents=incidents,
        hospitals=list(SHEFFIELD_HOSPITALS),
        category=DisasterCategory.CITY_WIDE_EMERGENCY,
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_GENERATORS = {
    DisasterCategory.GENERIC: generate_generic_scenario,
    DisasterCategory.FLOOD: generate_flood_scenario,
    DisasterCategory.INDUSTRIAL_ACCIDENT: generate_industrial_scenario,
    DisasterCategory.CITY_WIDE_EMERGENCY: generate_city_wide_scenario,
}


def generate_scenario_by_category(
    category: DisasterCategory,
    config: dict | None = None,
    seed: int = 42,
) -> DisasterScenario:
    """Dispatcher: route to the correct scenario generator for *category*.

    Args:
        category: One of the ``DisasterCategory`` enum values.
        config:   Configuration dict matching ``configs/default.toml`` structure.
        seed:     Random seed for deterministic output.

    Returns:
        A ``DisasterScenario`` appropriate for the given disaster type.

    Raises:
        KeyError: If ``category`` is not a known ``DisasterCategory``.
    """
    generator = _GENERATORS[category]
    return generator(config=config, seed=seed)
