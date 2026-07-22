"""
Decision Engine configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real


@dataclass(slots=True, frozen=True)
class DecisionEngineConfig:
    """
    Quantitative policy used by the Decision Engine.

    ``minimum_decision_score`` is evaluated after combining regime confidence
    with the available supporting evidence. ``confluence_weight`` is retained
    as the public compatibility name for the supporting-evidence weight because
    the engine may combine probability and confluence before applying it.
    """

    minimum_decision_score: float = 0.70
    regime_weight: float = 0.50
    confluence_weight: float = 0.50

    def __post_init__(self) -> None:
        """Validate the immutable decision policy at construction time."""

        minimum_score = self._validate_normalized(
            self.minimum_decision_score,
            name="minimum_decision_score",
        )
        regime_weight = self._validate_weight(
            self.regime_weight,
            name="regime_weight",
        )
        supporting_weight = self._validate_weight(
            self.confluence_weight,
            name="confluence_weight",
        )

        if regime_weight + supporting_weight <= 0.0:
            raise ValueError("decision weights must have a positive total")

        object.__setattr__(self, "minimum_decision_score", minimum_score)
        object.__setattr__(self, "regime_weight", regime_weight)
        object.__setattr__(self, "confluence_weight", supporting_weight)

    @property
    def total_weight(self) -> float:
        """Return the positive total decision weight."""

        return self.regime_weight + self.confluence_weight

    @property
    def normalized_regime_weight(self) -> float:
        """Return the regime share of the combined decision score."""

        return self.regime_weight / self.total_weight

    @property
    def normalized_supporting_evidence_weight(self) -> float:
        """Return the supporting-evidence share of the decision score."""

        return self.confluence_weight / self.total_weight

    @staticmethod
    def _validate_normalized(value: float, *, name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError(f"{name} must be a real number")
        normalized = float(value)
        if not isfinite(normalized) or not 0.0 <= normalized <= 1.0:
            raise ValueError(f"{name} must be finite and within [0, 1]")
        return normalized

    @staticmethod
    def _validate_weight(value: float, *, name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError(f"{name} must be a real number")
        normalized = float(value)
        if not isfinite(normalized) or normalized < 0.0:
            raise ValueError(f"{name} must be finite and non-negative")
        return normalized
