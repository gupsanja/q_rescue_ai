from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from q_rescue.domain.models import Ambulance, Incident
from q_rescue.simulation.distance_matrix import DistanceMatrix, SeverityMapping

Variable = tuple[str, str]
QuadraticTerm = tuple[Variable, Variable]


@dataclass
class QuboModel:
    """Framework-neutral QUBO representation: x^T Q x + constant."""

    objective_linear: dict[Variable, float] = field(default_factory=dict)
    linear: dict[Variable, float] = field(default_factory=dict)
    quadratic: dict[QuadraticTerm, float] = field(default_factory=dict)
    constant: float = 0.0

    @property
    def variables(self) -> list[Variable]:
        return list(self.linear)

    def evaluate(self, sample: dict[Variable, int]) -> float:
        value = self.constant
        value += sum(
            coefficient * sample.get(variable, 0) for variable, coefficient in self.linear.items()
        )
        value += sum(
            coefficient * sample.get(left, 0) * sample.get(right, 0)
            for (left, right), coefficient in self.quadratic.items()
        )
        return value


class AmbulanceAllocationQuboBuilder:
    """Build a POC QUBO for one-to-one ambulance/incident assignment.

    The solver now accepts a pre-computed ``DistanceMatrix`` and
    ``SeverityMapping`` from the simulation layer (Member 2), and applies
    the objective function internally:

        cost(a, i) = distance_weight * d(a, i) - severity_weight * s(i)

    A negative cost is expected for high-severity incidents: the QUBO
    minimiser is attracted toward strongly negative entries.
    """

    def __init__(
        self,
        distance_weight: float = 1.0,
        severity_weight: float = 8.0,
        constraint_penalty: float = 100.0,
        critical_priority: bool = False,
        demand_weight: float = 8.0,
    ) -> None:
        self.distance_weight = distance_weight
        self.severity_weight = severity_weight
        self.constraint_penalty = constraint_penalty
        self.critical_priority = critical_priority
        self.demand_weight = demand_weight
        self._ai_patch: dict | None = None

    def build(
        self,
        ambulances: list[Ambulance],
        incidents: list[Incident],
        distance_matrix: DistanceMatrix,
        severity_mapping: SeverityMapping,
    ) -> QuboModel:
        """Construct the QUBO model from pre-computed simulation outputs.

        If an AI patch has been applied via :meth:`apply_ai_patch`, the severity
        mapping is overridden with the patch's ``severity_overrides`` and
        ``demand_overrides`` add an urgency bonus for high predicted demand.

        Args:
            ambulances:       Ambulance list from the scenario.
            incidents:        Incident list from the scenario.
            distance_matrix:  Raw distances (km) from ``build_distance_matrix()``.
            severity_mapping: Absolute severity weights from ``build_severity_mapping()``.

        Returns:
            A populated ``QuboModel`` ready for the Qiskit solver.
        """
        # Apply AI severity overrides if a patch is present
        if self._ai_patch:
            severity_mapping = dict(severity_mapping)
            for iid, weight in self._ai_patch.get("severity_overrides", {}).items():
                if iid in severity_mapping:
                    severity_mapping[iid] = weight

        model = QuboModel()

        for ambulance in ambulances:
            for incident in incidents:
                variable = (ambulance.id, incident.id)
                distance = distance_matrix.matrix[ambulance.id][incident.id]
                severity = severity_mapping[incident.id]
                # Normalise severity to 0-1 range (schema: 25/50/75/100 -> 0.25...1.0)
                severity_normalised = severity / 100.0
                assignment_cost = (
                    self.distance_weight * distance - self.severity_weight * severity_normalised
                )
                model.objective_linear[variable] = assignment_cost
                model.linear[variable] = assignment_cost

        assignment_target = min(len(ambulances), len(incidents))
        self._add_cardinality_penalty(model, model.variables, assignment_target)
        if self.critical_priority:
            self._add_critical_priority_penalty(model, ambulances, incidents, severity_mapping)

        for ambulance in ambulances:
            variables = [(ambulance.id, incident.id) for incident in incidents]
            self._add_exclusion_penalties(model, variables)

        for incident in incidents:
            variables = [(ambulance.id, incident.id) for ambulance in ambulances]
            self._add_exclusion_penalties(model, variables)

        # Apply AI demand overrides as an urgency bonus per incident.
        if self._ai_patch:
            demand_overrides = self._ai_patch.get("demand_overrides", {})
            for ambulance in ambulances:
                for incident in incidents:
                    if incident.id in demand_overrides:
                        var = (ambulance.id, incident.id)
                        demand = float(demand_overrides[incident.id])
                        cost_delta = -self.demand_weight * demand
                        model.objective_linear[var] += cost_delta
                        model.linear[var] += cost_delta

        return model

    def apply_ai_patch(self, patch: dict | None) -> AmbulanceAllocationQuboBuilder:
        """Override severity and demand weights with AI predictions.

        Creates a new builder instance configured to use the AI-predicted
        weights for the specific scenario referenced in the patch.

        Args:
            patch: A ``QuboAIPatch`` dict containing ``severity_overrides`` and
                   ``demand_overrides``. If None, returns ``self`` (unpatched).

        Returns:
            A new ``AmbulanceAllocationQuboBuilder`` instance, or self.
        """
        if not patch:
            return self

        patched_builder = AmbulanceAllocationQuboBuilder(
            distance_weight=self.distance_weight,
            severity_weight=self.severity_weight,
            constraint_penalty=self.constraint_penalty,
            critical_priority=self.critical_priority,
            demand_weight=self.demand_weight,
        )
        patched_builder._ai_patch = patch
        return patched_builder

    def _add_cardinality_penalty(
        self,
        model: QuboModel,
        variables: list[Variable],
        target: int,
    ) -> None:
        """Add P(target - sum(x))^2 using x^2 = x for binary variables."""
        penalty = self.constraint_penalty
        model.constant += penalty * target**2

        for variable in variables:
            model.linear[variable] += penalty * (1 - 2 * target)

        for left, right in combinations(variables, 2):
            model.quadratic[(left, right)] = model.quadratic.get((left, right), 0.0) + 2 * penalty

    def _add_exclusion_penalties(self, model: QuboModel, variables: list[Variable]) -> None:
        for left, right in combinations(variables, 2):
            model.quadratic[(left, right)] = (
                model.quadratic.get((left, right), 0.0) + self.constraint_penalty
            )

    def _add_critical_priority_penalty(
        self,
        model: QuboModel,
        ambulances: list[Ambulance],
        incidents: list[Incident],
        severity_mapping: SeverityMapping,
    ) -> None:
        critical_incidents = [
            incident for incident in incidents if severity_mapping[incident.id] == 100
        ]
        target = min(len(ambulances), len(critical_incidents))
        if target == 0:
            return

        variables = [
            (ambulance.id, incident.id)
            for ambulance in ambulances
            for incident in critical_incidents
        ]
        self._add_cardinality_penalty(model, variables, target)
