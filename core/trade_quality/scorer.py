"""
Trade Quality Scoring Engine.

Calculates an overall trade quality score (0–100) from independent,
validated evidence components.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Final

from .models import (
    QualityLevel,
    QualityReason,
    TradeQuality,
)


@dataclass(
    slots=True,
    frozen=True,
)
class TradeQualityScorerConfig:
    """Weight and classification configuration for trade-quality scoring."""

    trend_weight: float = 20.0
    momentum_weight: float = 15.0
    volatility_weight: float = 15.0
    regime_confidence_weight: float = 20.0
    signal_confidence_weight: float = 15.0
    risk_reward_weight: float = 15.0

    trend_maximum: float = 10.0
    momentum_maximum: float = 10.0
    volatility_maximum: float = 10.0
    risk_reward_maximum: float = 3.0

    excellent_threshold: float = 90.0
    high_threshold: float = 75.0
    medium_threshold: float = 60.0
    low_threshold: float = 40.0

    confidence_disagreement_tolerance: float = 0.05

    def __post_init__(self) -> None:
        weights = {
            "trend_weight": self.trend_weight,
            "momentum_weight": self.momentum_weight,
            "volatility_weight": self.volatility_weight,
            "regime_confidence_weight": self.regime_confidence_weight,
            "signal_confidence_weight": self.signal_confidence_weight,
            "risk_reward_weight": self.risk_reward_weight,
        }
        for name, value in weights.items():
            _require_finite(value, name)
            if value < 0.0:
                raise ValueError(f"{name} must be non-negative")

        total_weight = sum(weights.values())
        if total_weight <= 0.0:
            raise ValueError("at least one scorer weight must be positive")
        if abs(total_weight - 100.0) > 1e-9:
            raise ValueError(
                "trade-quality weights must sum to 100.0; "
                f"received {total_weight}"
            )

        maximums = {
            "trend_maximum": self.trend_maximum,
            "momentum_maximum": self.momentum_maximum,
            "volatility_maximum": self.volatility_maximum,
            "risk_reward_maximum": self.risk_reward_maximum,
        }
        for name, value in maximums.items():
            _require_finite(value, name)
            if value <= 0.0:
                raise ValueError(f"{name} must be positive")

        thresholds = (
            self.low_threshold,
            self.medium_threshold,
            self.high_threshold,
            self.excellent_threshold,
        )
        for name, value in (
            ("low_threshold", self.low_threshold),
            ("medium_threshold", self.medium_threshold),
            ("high_threshold", self.high_threshold),
            ("excellent_threshold", self.excellent_threshold),
        ):
            _require_finite(value, name)
            if not 0.0 <= value <= 100.0:
                raise ValueError(f"{name} must be in [0, 100]")

        _require_finite(
            self.confidence_disagreement_tolerance,
            "confidence_disagreement_tolerance",
        )
        if not 0.0 <= self.confidence_disagreement_tolerance <= 1.0:
            raise ValueError(
                "confidence_disagreement_tolerance must be in [0, 1]"
            )

        if thresholds != tuple(sorted(thresholds)):
            raise ValueError(
                "quality thresholds must be ordered "
                "LOW <= MEDIUM <= HIGH <= EXCELLENT"
            )


@dataclass(slots=True, frozen=True)
class _Component:
    name: str
    raw_value: float
    maximum: float
    normalized_value: float
    weight: float
    contribution: float


class TradeQualityScorer:
    """Score the quality of a trading opportunity."""

    _CONFIDENCE_COMPONENT_NAMES: Final[tuple[str, str]] = (
        "regime_confidence",
        "signal_confidence",
    )

    def __init__(
        self,
        config: TradeQualityScorerConfig | None = None,
    ) -> None:
        self._config = config or TradeQualityScorerConfig()

    @property
    def config(self) -> TradeQualityScorerConfig:
        """Return the immutable scorer configuration."""

        return self._config

    @staticmethod
    def _component(
        *,
        name: str,
        value: float,
        maximum: float,
        weight: float,
    ) -> _Component:
        _require_finite(value, name)
        if value < 0.0:
            raise ValueError(f"{name} must be non-negative")
        if value > maximum:
            raise ValueError(
                f"{name} must be <= {maximum}; received {value}"
            )

        normalized = value / maximum
        contribution = normalized * weight
        return _Component(
            name=name,
            raw_value=value,
            maximum=maximum,
            normalized_value=normalized,
            weight=weight,
            contribution=contribution,
        )

    def score(
        self,
        *,
        trend_score: float,
        momentum_score: float,
        volatility_score: float,
        regime_confidence: float,
        signal_confidence: float,
        risk_reward_ratio: float,
    ) -> TradeQuality:
        """Calculate and explain trade quality."""

        components = (
            self._component(
                name="trend",
                value=trend_score,
                maximum=self._config.trend_maximum,
                weight=self._config.trend_weight,
            ),
            self._component(
                name="momentum",
                value=momentum_score,
                maximum=self._config.momentum_maximum,
                weight=self._config.momentum_weight,
            ),
            self._component(
                name="volatility",
                value=volatility_score,
                maximum=self._config.volatility_maximum,
                weight=self._config.volatility_weight,
            ),
            self._component(
                name="regime_confidence",
                value=regime_confidence,
                maximum=1.0,
                weight=self._config.regime_confidence_weight,
            ),
            self._component(
                name="signal_confidence",
                value=signal_confidence,
                maximum=1.0,
                weight=self._config.signal_confidence_weight,
            ),
            self._component(
                name="risk_reward",
                value=risk_reward_ratio,
                maximum=self._config.risk_reward_maximum,
                weight=self._config.risk_reward_weight,
            ),
        )

        component_by_name = {
            component.name: component
            for component in components
        }
        trend = component_by_name["trend"].normalized_value
        momentum = component_by_name["momentum"].normalized_value
        volatility = component_by_name["volatility"].normalized_value
        rc = component_by_name["regime_confidence"].normalized_value
        sc = component_by_name["signal_confidence"].normalized_value

        quality = TradeQuality()
        quality.add_reason(
            QualityReason.STRONG_TREND
            if trend >= 0.70
            else QualityReason.WEAK_TREND
        )
        quality.add_reason(
            QualityReason.HIGH_MOMENTUM
            if momentum >= 0.70
            else QualityReason.LOW_MOMENTUM
        )
        quality.add_reason(
            QualityReason.GOOD_VOLATILITY
            if volatility >= 0.50
            else QualityReason.LOW_VOLATILITY
        )
        quality.add_reason(
            QualityReason.REGIME_CONFIRMED
            if rc >= 0.80
            else QualityReason.REGIME_UNCERTAIN
        )
        quality.add_reason(
            QualityReason.HIGH_CONFIDENCE
            if sc >= 0.80
            else QualityReason.LOW_CONFIDENCE
        )
        quality.add_reason(
            QualityReason.EXCELLENT_RISK_REWARD
            if risk_reward_ratio >= 2.0
            else QualityReason.POOR_RISK_REWARD
        )

        score = sum(component.contribution for component in components)
        quality.score = round(score, 2)
        quality.confidence = round(
            self._combined_confidence(rc=rc, sc=sc),
            6,
        )
        quality.level = self._classify(score)

        quality.metadata["scoring_scale"] = "0_TO_100"
        quality.metadata["weight_total"] = 100.0
        quality.metadata["confidence_method"] = (
            "WEAKER_EVIDENCE_PLUS_TOLERANCE_CAP"
        )
        quality.metadata["confidence_disagreement_tolerance"] = (
            self._config.confidence_disagreement_tolerance
        )
        quality.metadata["components"] = {
            component.name: {
                "raw_value": component.raw_value,
                "maximum": component.maximum,
                "normalized_value": component.normalized_value,
                "weight": component.weight,
                "contribution": component.contribution,
            }
            for component in components
        }
        quality.metadata["score_before_rounding"] = score
        quality.metadata["classification_thresholds"] = {
            "low": self._config.low_threshold,
            "medium": self._config.medium_threshold,
            "high": self._config.high_threshold,
            "excellent": self._config.excellent_threshold,
        }

        return quality

    def _combined_confidence(
        self,
        *,
        rc: float,
        sc: float,
    ) -> float:
        """
        Combine confidence without allowing one strong source to hide another.

        Closely agreeing sources retain the stronger value. When disagreement
        exceeds the configured tolerance, confidence is capped relative to the
        weaker source.
        """

        stronger = max(rc, sc)
        weaker = min(rc, sc)
        return min(
            stronger,
            weaker + self._config.confidence_disagreement_tolerance,
        )

    def _classify(self, score: float) -> QualityLevel:
        if score >= self._config.excellent_threshold:
            return QualityLevel.EXCELLENT
        if score >= self._config.high_threshold:
            return QualityLevel.HIGH
        if score >= self._config.medium_threshold:
            return QualityLevel.MEDIUM
        if score >= self._config.low_threshold:
            return QualityLevel.LOW
        return QualityLevel.REJECTED


def _require_finite(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    if not isfinite(float(value)):
        raise ValueError(f"{name} must be finite")
