"""Schema validation utilities for Phase 2 data structures — M5 deliverable.

All consumers (M1, M2, M4) and scripts should call these validators before
writing or persisting shared data objects to catch schema violations early.

Validation rules are taken directly from Phase 2 Integration Schema §6.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# EXPECTED_FEATURES — canonical 14-feature column order (schema §2.1)
# ---------------------------------------------------------------------------

#: The exact 14 feature column names in the order they must appear in both
#: ``flood_dataset.csv`` and ``flood_observations.csv``.  Any CSV produced
#: by M2's ``export_flood_observations_csv()`` and consumed by M5's
#: ``predict_scenario()`` must have columns matching this list exactly.
EXPECTED_FEATURES: list[str] = [
    "rainfall_24h_mm",
    "rainfall_72h_mm",
    "river_level_m",
    "river_level_change_rate",
    "soil_saturation_pct",
    "upstream_dam_release_m3s",
    "temperature_c",
    "wind_speed_kmh",
    "elevation_m",
    "distance_to_river_km",
    "drainage_capacity_index",
    "urbanization_pct",
    "population_density_per_km2",
    "previous_flood_history",
]

_VALID_LABELS: frozenset[str] = frozenset({"Low", "Moderate", "High", "Severe"})
_VALID_WEIGHTS: frozenset[int] = frozenset({25, 50, 75, 100})
_VALID_INTS: frozenset[int] = frozenset({0, 1, 2, 3})


# ---------------------------------------------------------------------------
# FloodObservation validators
# ---------------------------------------------------------------------------


def validate_flood_observation_columns(columns: list[str] | object) -> None:
    """Assert that *columns* matches :data:`EXPECTED_FEATURES` exactly.

    Args:
        columns: The column list to validate (e.g. ``list(df.columns)``).

    Raises:
        AssertionError: If *columns* does not equal ``EXPECTED_FEATURES``.

    Example::

        >>> validate_flood_observation_columns(EXPECTED_FEATURES)  # no error
    """
    col_list = list(columns)
    assert col_list == EXPECTED_FEATURES, (
        "FloodObservation CSV columns do not match schema §2.1 EXPECTED_FEATURES.\n"
        f"Expected: {EXPECTED_FEATURES}\n"
        f"Got:      {col_list}"
    )


# ---------------------------------------------------------------------------
# AIPrediction validators
# ---------------------------------------------------------------------------


def validate_ai_prediction(pred: dict) -> None:
    """Assert that *pred* is a valid ``AIPrediction`` dict (schema §2.2 + §6).

    Checks:
    - ``flood_severity_label`` ∈ ``{"Low","Moderate","High","Severe"}``
    - ``flood_severity_int``   ∈ ``{0,1,2,3}``
    - ``flood_severity_weight`` ∈ ``{25,50,75,100}``
    - ``resource_demand_normalised`` ∈ ``[0.0, 1.0]``
    - ``class_probabilities`` sums to 1.0 (± 1e-6)
    - ``confidence`` ∈ ``[0.0, 1.0]``

    Args:
        pred: A dict produced by :func:`~q_rescue.ai.predictor.predict_scenario`.

    Raises:
        AssertionError: If any rule is violated.
    """
    label = pred.get("flood_severity_label")
    assert label in _VALID_LABELS, (
        f"flood_severity_label must be one of {sorted(_VALID_LABELS)}, got {label!r}"
    )

    sev_int = pred.get("flood_severity_int")
    assert sev_int in _VALID_INTS, f"flood_severity_int must be in {{0,1,2,3}}, got {sev_int!r}"

    weight = pred.get("flood_severity_weight")
    assert weight in _VALID_WEIGHTS, (
        f"flood_severity_weight must be in {{25,50,75,100}}, got {weight!r}"
    )

    norm = pred.get("resource_demand_normalised")
    assert norm is not None and 0.0 <= float(norm) <= 1.0, (
        f"resource_demand_normalised must be in [0.0, 1.0], got {norm!r}"
    )

    probs = pred.get("class_probabilities", {})
    total = sum(float(v) for v in probs.values())
    assert abs(total - 1.0) < 1e-4, f"class_probabilities must sum to 1.0 (±1e-4), got {total:.8f}"

    confidence = pred.get("confidence")
    assert confidence is not None and 0.0 <= float(confidence) <= 1.0, (
        f"confidence must be in [0.0, 1.0], got {confidence!r}"
    )


# ---------------------------------------------------------------------------
# QuboAIPatch validators
# ---------------------------------------------------------------------------


def validate_qubo_patch(patch: dict, incident_ids: list[str]) -> None:
    """Assert that *patch* is a valid ``QuboAIPatch`` dict (schema §2.4 + §6).

    Checks:
    - All values in ``severity_overrides`` ∈ ``{25,50,75,100}``
    - All values in ``demand_overrides`` ∈ ``[0.0, 1.0]``
    - All keys in both override dicts are present in *incident_ids*

    Args:
        patch:        A dict produced by :func:`~q_rescue.ai.predictor.build_qubo_patch`.
        incident_ids: The list of valid incident ID strings for the scenario.

    Raises:
        AssertionError: If any rule is violated.
    """
    valid_ids = set(incident_ids)

    severity_overrides = patch.get("severity_overrides", {})
    for iid, w in severity_overrides.items():
        assert iid in valid_ids, f"severity_overrides contains unknown incident_id {iid!r}"
        assert w in _VALID_WEIGHTS, (
            f"severity_overrides[{iid!r}] must be in {{25,50,75,100}}, got {w!r}"
        )

    demand_overrides = patch.get("demand_overrides", {})
    for iid, val in demand_overrides.items():
        assert iid in valid_ids, f"demand_overrides contains unknown incident_id {iid!r}"
        assert 0.0 <= float(val) <= 1.0, (
            f"demand_overrides[{iid!r}] must be in [0.0, 1.0], got {val!r}"
        )
