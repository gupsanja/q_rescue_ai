"""Cost matrix construction for the Q-Rescue ambulance-incident assignment problem.

Provides the ``CostMatrix`` dataclass and ``build_cost_matrix()`` factory.
The matrix feeds directly into:
- ``AmbulanceAllocationQuboBuilder.build()`` (Member 1)
- ``GreedyAllocator.solve()`` (Member 4, via scenario)
- CSV/JSON exports (this module's own ``to_dataframe()`` / ``to_dict()``)

Severity–distance cost formula
-------------------------------
    cost(a, i) = distance_weight × d(a, i)  −  severity_weight × s(i)

A negative cost is expected for high-severity incidents: the QUBO solver
*minimises* total cost, so strongly negative entries attract assignment.
Refer to ``docs/optimisation_model.md`` for the full mathematical derivation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from q_rescue.domain.models import Location, Severity
from q_rescue.simulation.generator import DisasterScenario


# Severity → QUBO scalar (IntEnum 1-4).  Multiply by severity_weight (8.0)
# to get the effective weight used in cost calculation.
# Absolute spec weights (25/50/75/100) are stored in Severity.absolute_weight().
_SEVERITY_SCALAR: dict[Severity, int] = {
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


@dataclass
class CostMatrix:
    """Ambulance-to-incident cost matrix with auxiliary distance data.

    Attributes:
        matrix:        Nested dict ``{ambulance_id: {incident_id: cost}}``.
        distances:     Raw Haversine distances in km between every pair.
        ambulance_ids: Ordered list of ambulance IDs (row index).
        incident_ids:  Ordered list of incident IDs (column index).
    """

    matrix: dict[str, dict[str, float]] = field(default_factory=dict)
    distances: dict[str, dict[str, float]] = field(default_factory=dict)
    ambulance_ids: list[str] = field(default_factory=list)
    incident_ids: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, dict[str, float]]:
        """Return the cost matrix as a plain nested dict (JSON-serialisable)."""
        return self.matrix

    def to_dataframe(self):  # -> pd.DataFrame
        """Return the cost matrix as a pandas DataFrame (rows=ambulances, cols=incidents).

        Raises:
            ImportError: If ``pandas`` is not installed.
        """
        import pandas as pd  # noqa: PLC0415

        return pd.DataFrame(self.matrix).T.reindex(
            index=self.ambulance_ids, columns=self.incident_ids
        )

    def to_numpy(self):  # -> np.ndarray
        """Return cost values as a 2-D NumPy array (rows=ambulances, cols=incidents).

        Raises:
            ImportError: If ``numpy`` is not installed.
        """
        import numpy as np  # noqa: PLC0415

        return np.array(
            [
                [self.matrix[a_id][i_id] for i_id in self.incident_ids]
                for a_id in self.ambulance_ids
            ],
            dtype=float,
        )

    def distances_dataframe(self):  # -> pd.DataFrame
        """Return raw Haversine distance (km) as a DataFrame."""
        import pandas as pd  # noqa: PLC0415

        return pd.DataFrame(self.distances).T.reindex(
            index=self.ambulance_ids, columns=self.incident_ids
        )


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------


def build_cost_matrix(
    scenario: DisasterScenario,
    distance_weight: float = 1.0,
    severity_weight: float = 8.0,
    distance_fn: Callable[[Location, Location], float] | None = None,
) -> CostMatrix:
    """Build a weighted ambulance-to-incident cost matrix from a scenario.

    Args:
        scenario:        A ``DisasterScenario`` produced by any generator.
        distance_weight: Multiplier for the distance component of cost.
        severity_weight: Multiplier for the severity component of cost.
                         Higher values make the solver prioritise critical
                         incidents more strongly over distance.
        distance_fn:     Optional custom distance function
                         ``(Location, Location) -> float`` in km.
                         Defaults to Haversine (great-circle) distance.
                         Pass ``SheffieldRoadNetwork().shortest_path_distance``
                         to use road-network distances (Phase 6).

    Returns:
        A populated ``CostMatrix`` instance.

    Example::

        scenario = generate_flood_scenario()
        cm = build_cost_matrix(scenario, distance_weight=1.0, severity_weight=8.0)
        df = cm.to_dataframe()
    """
    dist = distance_fn if distance_fn is not None else _haversine

    ambulance_ids = [a.id for a in scenario.ambulances]
    incident_ids = [i.id for i in scenario.incidents]

    matrix: dict[str, dict[str, float]] = {}
    distances: dict[str, dict[str, float]] = {}

    for ambulance in scenario.ambulances:
        matrix[ambulance.id] = {}
        distances[ambulance.id] = {}

        for incident in scenario.incidents:
            d = dist(ambulance.location, incident.location)
            sev_scalar = _SEVERITY_SCALAR.get(incident.severity, 1)
            cost = (distance_weight * d) - (severity_weight * sev_scalar)

            matrix[ambulance.id][incident.id] = round(cost, 6)
            distances[ambulance.id][incident.id] = round(d, 6)

    return CostMatrix(
        matrix=matrix,
        distances=distances,
        ambulance_ids=ambulance_ids,
        incident_ids=incident_ids,
    )


def _haversine(loc1: Location, loc2: Location) -> float:
    """Default distance function: great-circle distance in km."""
    return loc1.haversine_to(loc2)
