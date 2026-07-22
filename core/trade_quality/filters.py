"""
Trade quality filtering rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Final

from .models import QualityLevel, QualityReason, TradeQuality

LEVEL_ORDER: Final[dict[QualityLevel, int]] = {
    QualityLevel.REJECTED: 0,
    QualityLevel.LOW: 1,
    QualityLevel.MEDIUM: 2,
    QualityLevel.HIGH: 3,
    QualityLevel.EXCELLENT: 4,
}


@dataclass(
    slots=True,
    frozen=True,
)
class TradeQualityFilterConfig:
    """Configuration for trade-quality acceptance."""

    minimum_score: float = 60.0
    minimum_confidence: float = 0.70
    minimum_level: QualityLevel = QualityLevel.MEDIUM

    def __post_init__(self) -> None:
        _require_finite_number(self.minimum_score, "minimum_score")
        if not 0.0 <= self.minimum_score <= 100.0:
            raise ValueError("minimum_score must be in [0, 100]")

        _require_finite_number(
            self.minimum_confidence,
            "minimum_confidence",
        )
        if not 0.0 <= self.minimum_confidence <= 1.0:
            raise ValueError("minimum_confidence must be in [0, 1]")

        if not isinstance(self.minimum_level, QualityLevel):
            raise TypeError("minimum_level must be a QualityLevel")


class TradeQualityFilter:
    """Apply explicit acceptance rules to a trade-quality evaluation."""

    def __init__(
        self,
        config: TradeQualityFilterConfig | None = None,
    ) -> None:
        self._config = config or TradeQualityFilterConfig()

    @property
    def config(self) -> TradeQualityFilterConfig:
        """Return the immutable filter configuration."""

        return self._config

    @property
    def minimum_level_order(self) -> int:
        """Return the numeric order of the configured minimum level."""

        return LEVEL_ORDER[self._config.minimum_level]

    def passes(self, quality: TradeQuality) -> bool:
        """Return whether all independent quality requirements pass."""

        checks = self._evaluate_checks(quality)
        return all(checks.values())

    def apply(self, quality: TradeQuality) -> TradeQuality:
        """Apply the filter and attach deterministic diagnostics."""

        checks = self._evaluate_checks(quality)
        approved = all(checks.values())
        quality.approved = approved

        quality.add_reason(
            QualityReason.PASSED if approved else QualityReason.REJECTED
        )
        quality.metadata["filter"] = {
            "minimum_score": self._config.minimum_score,
            "minimum_confidence": self._config.minimum_confidence,
            "minimum_level": self._config.minimum_level.value,
            "checks": checks,
            "failed_checks": [
                name for name, passed in checks.items() if not passed
            ],
        }
        return quality

    def _evaluate_checks(self, quality: TradeQuality) -> dict[str, bool]:
        """Validate a result and evaluate each acceptance condition."""

        self._validate_quality(quality)
        return {
            "score": quality.score >= self._config.minimum_score,
            "confidence": (
                quality.confidence >= self._config.minimum_confidence
            ),
            "level": (
                LEVEL_ORDER[quality.level] >= self.minimum_level_order
            ),
        }

    @staticmethod
    def _validate_quality(quality: TradeQuality) -> None:
        if not isinstance(quality, TradeQuality):
            raise TypeError("quality must be a TradeQuality")

        _require_finite_number(quality.score, "quality.score")
        if not 0.0 <= quality.score <= 100.0:
            raise ValueError("quality.score must be in [0, 100]")

        _require_finite_number(
            quality.confidence,
            "quality.confidence",
        )
        if not 0.0 <= quality.confidence <= 1.0:
            raise ValueError("quality.confidence must be in [0, 1]")

        if not isinstance(quality.level, QualityLevel):
            raise TypeError("quality.level must be a QualityLevel")


def _require_finite_number(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    if not isfinite(float(value)):
        raise ValueError(f"{name} must be finite")
