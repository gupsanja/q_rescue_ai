from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from math import hypot


class Severity(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass(frozen=True)
class Location:
    x: float
    y: float

    def distance_to(self, other: "Location") -> float:
        return hypot(self.x - other.x, self.y - other.y)


@dataclass(frozen=True)
class Ambulance:
    id: str
    location: Location


@dataclass(frozen=True)
class Incident:
    id: str
    location: Location
    severity: Severity


@dataclass(frozen=True)
class Assignment:
    ambulance_id: str
    incident_id: str
    distance: float


@dataclass
class OptimizationResult:
    assignments: list[Assignment]
    objective_value: float
    solver_name: str
    feasible: bool = True
    metadata: dict[str, object] = field(default_factory=dict)

