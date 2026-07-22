"""
Weight recommendation model.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class WeightRecommendation:
    """
    Recommended weight for an engineered feature.
    """

    feature_name: str

    current_weight: float

    recommended_weight: float

    confidence: float

    reason: str

    @property
    def has_change(self) -> bool:
        """
        Whether the recommendation changes the current weight.
        """

        return self.current_weight != self.recommended_weight