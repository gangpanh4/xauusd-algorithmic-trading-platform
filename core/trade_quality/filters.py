"""
Trade quality filtering rules.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import QualityLevel, TradeQuality

LEVEL_ORDER = {
    QualityLevel.REJECTED: 0,
    QualityLevel.LOW: 1,
    QualityLevel.MEDIUM: 2,
    QualityLevel.HIGH: 3,
    QualityLevel.EXCELLENT: 4,
}


@dataclass(slots=True)
class TradeQualityFilterConfig:
    """
    Configuration for trade quality filtering.
    """

    minimum_score: float = 70.0
    minimum_confidence: float = 0.70
    minimum_level: QualityLevel = QualityLevel.MEDIUM


class TradeQualityFilter:
    """
    Applies acceptance rules to a TradeQuality evaluation.
    """

    def __init__(
        self,
        config: TradeQualityFilterConfig | None = None,
    ) -> None:
        self._config = config or TradeQualityFilterConfig()

    @property
    def config(self) -> TradeQualityFilterConfig:
        return self._config

    def passes(
        self,
        quality: TradeQuality,
    ) -> bool:
        """
        Returns True if the trade satisfies all quality requirements.
        """

        if quality.score < self._config.minimum_score:
            return False

        if quality.confidence < self._config.minimum_confidence:
            return False

        if LEVEL_ORDER[quality.level] < LEVEL_ORDER[self._config.minimum_level]:
            return False

        return True

    def apply(
        self,
        quality: TradeQuality,
    ) -> TradeQuality:
        """
        Updates the TradeQuality object with the final approval result.
        """

        quality.approved = self.passes(quality)
        return quality