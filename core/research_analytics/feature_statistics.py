"""
Feature statistics models.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class FeatureStatistics:
    """
    Statistics describing a single engineered feature.
    """

    feature_name: str

    count: int

    minimum: float

    maximum: float

    mean: float

    winner_mean: float

    loser_mean: float

    @property
    def gap(self) -> float:
        """
        Difference between winners and losers.
        """

        return (
            self.winner_mean
            - self.loser_mean
        )

    @property
    def has_separation(
        self,
    ) -> bool:
        """
        Whether the feature produces any measurable
        separation between winners and losers.
        """

        return self.gap != 0.0