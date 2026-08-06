"""Canonical severity label mappings — M5 deliverable (Phase 2, Week 1).

This is the *single source of truth* for converting between the four
representation layers defined in Phase 2 Integration Schema §1:

    XGBoost label string  →  canonical int  →  Severity enum  →  QUBO weight
    ──────────────────────────────────────────────────────────────────────────
    "Low"                 →  0              →  Severity.LOW    →  25
    "Moderate"            →  1              →  Severity.MEDIUM →  50
    "High"                →  2              →  Severity.HIGH   →  75
    "Severe"              →  3              →  Severity.CRITICAL → 100

All consumers (M1, M3, M4) must use these functions instead of comparing
raw strings directly.

> [!WARNING]
> "Moderate" ≠ "MEDIUM" and "Severe" ≠ "CRITICAL" as raw strings.
> Always go through the canonical int or the helpers below.
"""

from __future__ import annotations

import numpy as np

from q_rescue.domain.models import Severity

# ---------------------------------------------------------------------------
# Canonical constants (schema §1)
# ---------------------------------------------------------------------------

#: Ordered list of AI label strings, Low=index-0 … Severe=index-3.
#: This order is the canonical encoding for XGBoost class indices.
SEVERITY_ORDER: list[str] = ["Low", "Moderate", "High", "Severe"]

#: AI label string → canonical integer (schema §1, "Canonical Int" column).
AI_LABEL_TO_INT: dict[str, int] = {
    "Low": 0,
    "Moderate": 1,
    "High": 2,
    "Severe": 3,
}

#: AI label string → Severity enum name string (schema §1, "Codebase Enum" column).
AI_LABEL_TO_SEVERITY_ENUM: dict[str, str] = {
    "Low": "LOW",
    "Moderate": "MEDIUM",
    "High": "HIGH",
    "Severe": "CRITICAL",
}

#: AI label string → QUBO absolute weight (schema §1, "Absolute QUBO Weight" column).
AI_LABEL_TO_WEIGHT: dict[str, int] = {
    "Low": 25,
    "Moderate": 50,
    "High": 75,
    "Severe": 100,
}

#: Inverse map: canonical int → AI label string.
INT_TO_AI_LABEL: dict[int, str] = {v: k for k, v in AI_LABEL_TO_INT.items()}


# ---------------------------------------------------------------------------
# Public helper functions (schema §3.2 — M5 creates label_mapper.py)
# ---------------------------------------------------------------------------


def ai_label_to_severity(label: str) -> Severity:
    """Map XGBoost label string to the domain ``Severity`` enum.

    Args:
        label: One of ``"Low"``, ``"Moderate"``, ``"High"``, ``"Severe"``.

    Returns:
        The corresponding ``Severity`` enum member.

    Raises:
        KeyError: If *label* is not a recognised canonical severity label.

    Example::

        >>> ai_label_to_severity("High")
        <Severity.HIGH: 3>
    """
    enum_name = AI_LABEL_TO_SEVERITY_ENUM[label]
    return Severity[enum_name]


def ai_label_to_weight(label: str) -> int:
    """Map XGBoost label string to the QUBO absolute weight (25 / 50 / 75 / 100).

    Args:
        label: One of ``"Low"``, ``"Moderate"``, ``"High"``, ``"Severe"``.

    Returns:
        The absolute severity weight as defined in schema §1.

    Raises:
        KeyError: If *label* is not a recognised canonical severity label.

    Example::

        >>> ai_label_to_weight("Severe")
        100
    """
    return AI_LABEL_TO_WEIGHT[label]


# ---------------------------------------------------------------------------
# CanonicalSeverityEncoder
# ---------------------------------------------------------------------------


class CanonicalSeverityEncoder:
    """Sklearn-compatible label encoder that uses the *canonical* int ordering.

    ``sklearn.LabelEncoder`` sorts classes alphabetically, which maps
    ``"High"→0, "Low"→1, "Moderate"→2, "Severe"→3`` — silently wrong
    relative to schema §1 (``Low=0, Moderate=1, High=2, Severe=3``).

    This encoder is a drop-in replacement that always uses the canonical
    ordering defined in :data:`AI_LABEL_TO_INT`.

    It is serialisable via :mod:`joblib` and is saved to
    ``flood_xgboost_project/outputs/label_encoder.joblib``.
    """

    def __init__(self) -> None:
        self.classes_: list[str] = SEVERITY_ORDER

    # ------------------------------------------------------------------
    # sklearn-compatible interface
    # ------------------------------------------------------------------

    def fit(self, y: list[str] | np.ndarray) -> CanonicalSeverityEncoder:
        """No-op fit; the mapping is fixed by the schema, not the data."""
        return self

    def transform(self, y: list[str] | np.ndarray | object) -> np.ndarray:
        """Encode label strings → canonical ints (0=Low … 3=Severe).

        Args:
            y: An iterable / Series / array of label strings.

        Returns:
            A NumPy int array of shape ``(n,)``.
        """
        return np.array([AI_LABEL_TO_INT[str(label)] for label in y], dtype=np.int64)

    def inverse_transform(self, y: list[int] | np.ndarray) -> list[str]:
        """Decode canonical ints → label strings.

        Args:
            y: An iterable of ints in ``{0, 1, 2, 3}``.

        Returns:
            A list of label strings.
        """
        return [INT_TO_AI_LABEL[int(i)] for i in y]

    def fit_transform(self, y: list[str] | np.ndarray | object) -> np.ndarray:
        """Fit (no-op) then transform."""
        return self.fit(y).transform(y)
