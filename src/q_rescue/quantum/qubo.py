from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from q_rescue.domain.models import Ambulance, Incident

Variable = tuple[str, str]
QuadraticTerm = tuple[Variable, Variable]


@dataclass
class QuboModel:
    """Framework-neutral QUBO representation: x^T Q x + constant."""

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

    Linear costs balance travel distance against severity coverage. Pairwise
    penalties prevent an ambulance serving multiple incidents and an incident
    receiving multiple ambulances in the same optimisation period.
    """

    def __init__(
        self,
        distance_weight: float = 1.0,
        severity_weight: float = 8.0,
        constraint_penalty: float = 100.0,
    ) -> None:
        self.distance_weight = distance_weight
        self.severity_weight = severity_weight
        self.constraint_penalty = constraint_penalty

    def build(self, ambulances: list[Ambulance], incidents: list[Incident]) -> QuboModel:
        model = QuboModel()

        for ambulance in ambulances:
            for incident in incidents:
                variable = (ambulance.id, incident.id)
                distance = ambulance.location.distance_to(incident.location)
                model.linear[variable] = (
                    self.distance_weight * distance
                    - self.severity_weight * float(incident.severity)
                )

        for ambulance in ambulances:
            variables = [(ambulance.id, incident.id) for incident in incidents]
            self._add_exclusion_penalties(model, variables)

        for incident in incidents:
            variables = [(ambulance.id, incident.id) for ambulance in ambulances]
            self._add_exclusion_penalties(model, variables)

        return model

    def _add_exclusion_penalties(self, model: QuboModel, variables: list[Variable]) -> None:
        for left, right in combinations(variables, 2):
            model.quadratic[(left, right)] = (
                model.quadratic.get((left, right), 0.0) + self.constraint_penalty
            )
