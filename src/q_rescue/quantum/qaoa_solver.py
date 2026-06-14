from __future__ import annotations

from itertools import product
from typing import Protocol

from q_rescue.quantum.qubo import QuboModel, Variable


class QuboSolver(Protocol):
    name: str

    def solve(self, model: QuboModel) -> tuple[dict[Variable, int], float]: ...


class ExactQuboSolver:
    """Dependency-free POC solver. Use only for small validation scenarios."""

    name = "exact-enumeration"

    def solve(self, model: QuboModel) -> tuple[dict[Variable, int], float]:
        variables = model.variables
        if len(variables) > 24:
            raise ValueError("Exact enumeration is limited to 24 binary variables")

        best_sample: dict[Variable, int] = {}
        best_value = float("inf")
        for bits in product((0, 1), repeat=len(variables)):
            sample = dict(zip(variables, bits, strict=True))
            value = model.evaluate(sample)
            if value < best_value:
                best_sample = sample
                best_value = value
        return best_sample, best_value


class QiskitQAOASolver:
    """Member 1 integration boundary for Qiskit Optimization and QAOA."""

    name = "qiskit-qaoa"

    def __init__(self, reps: int = 1, shots: int = 1024, seed: int = 42) -> None:
        self.reps = reps
        self.shots = shots
        self.seed = seed

    def solve(self, model: QuboModel) -> tuple[dict[Variable, int], float]:
        raise NotImplementedError(
            "Translate QuboModel into a Qiskit QuadraticProgram, run QAOA, "
            "and map the result back to the tuple-based variables."
        )
