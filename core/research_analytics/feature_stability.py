"""
Feature stability model.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class FeatureStability:
    """
    Describes how stable a feature is across trades.
    """

    feature_name: str

    observations: int

    stability_score: float

    winner_variance: float

    loser_variance: float

    reason: str

    @property
    def has_observations(self) -> bool:
        """
        Whether this feature was observed at least once.
        """

        return self.observations > 0