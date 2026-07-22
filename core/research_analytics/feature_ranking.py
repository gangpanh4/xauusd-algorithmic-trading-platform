"""
Feature ranking models.

Represents the statistical importance of engineered features.
"""

from __future__ import annotations

from dataclasses import dataclass
from core.research_analytics.config import (
    ResearchAnalyticsConfig,
)

_CONFIG = ResearchAnalyticsConfig()


@dataclass(slots=True, frozen=True)
class FeatureRanking:
    """
    Statistics describing a single engineered feature.
    """

    feature_name: str
    winner_average: float
    loser_average: float
    importance_score: float = 0.0

    @property
    def gap(self) -> float:
        """
        Difference between winners and losers.
        """
        return self.winner_average - self.loser_average

    @property
    def recommendation(self) -> str:
        """
        Human-readable recommendation.
        """
        config = _CONFIG

        if self.gap >= config.increase_threshold:
            return "Increase"

        if self.gap <= config.decrease_threshold:
            return "Decrease"

        if abs(self.gap) <= config.investigate_threshold:
            return "Investigate"

        return "Neutral"