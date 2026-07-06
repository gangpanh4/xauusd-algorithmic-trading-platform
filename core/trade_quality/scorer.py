"""
Trade Quality Scoring Engine.

Calculates an overall trade quality score (0–100) based on
multiple evidence sources.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import (
    QualityLevel,
    QualityReason,
    TradeQuality,
)


@dataclass(slots=True)
class TradeQualityScorerConfig:
    """
    Weight configuration for trade quality scoring.
    """

    trend_weight: float = 20.0
    momentum_weight: float = 15.0
    volatility_weight: float = 15.0
    regime_confidence_weight: float = 20.0
    signal_confidence_weight: float = 15.0
    risk_reward_weight: float = 15.0


class TradeQualityScorer:
    """
    Scores the quality of a trading opportunity.
    """

    def __init__(
        self,
        config: TradeQualityScorerConfig | None = None,
    ) -> None:
        self._config = config or TradeQualityScorerConfig()

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
        """
        Calculate trade quality.

        Returns
        -------
        TradeQuality
        """

        quality = TradeQuality()

        score = 0.0

        # ---------------------------------------------
        # Trend
        # ---------------------------------------------
        trend = min(max(trend_score / 10.0, 0.0), 1.0)
        score += trend * self._config.trend_weight

        if trend >= 0.70:
            quality.add_reason(QualityReason.STRONG_TREND)
        else:
            quality.add_reason(QualityReason.WEAK_TREND)

        # ---------------------------------------------
        # Momentum
        # ---------------------------------------------
        momentum = min(max(momentum_score / 10.0, 0.0), 1.0)
        score += momentum * self._config.momentum_weight

        if momentum >= 0.70:
            quality.add_reason(QualityReason.HIGH_MOMENTUM)
        else:
            quality.add_reason(QualityReason.LOW_MOMENTUM)

        # ---------------------------------------------
        # Volatility
        # ---------------------------------------------
        volatility = min(max(volatility_score / 10.0, 0.0), 1.0)
        score += volatility * self._config.volatility_weight

        if volatility >= 0.50:
            quality.add_reason(QualityReason.GOOD_VOLATILITY)
        else:
            quality.add_reason(QualityReason.LOW_VOLATILITY)

        # ---------------------------------------------
        # Regime Confidence
        # ---------------------------------------------
        rc = min(max(regime_confidence, 0.0), 1.0)
        score += rc * self._config.regime_confidence_weight

        if rc >= 0.80:
            quality.add_reason(QualityReason.REGIME_CONFIRMED)
        else:
            quality.add_reason(QualityReason.REGIME_UNCERTAIN)

        # ---------------------------------------------
        # Signal Confidence
        # ---------------------------------------------
        sc = min(max(signal_confidence, 0.0), 1.0)
        score += sc * self._config.signal_confidence_weight

        if sc >= 0.80:
            quality.add_reason(QualityReason.HIGH_CONFIDENCE)
        else:
            quality.add_reason(QualityReason.LOW_CONFIDENCE)

        # ---------------------------------------------
        # Risk / Reward
        # ---------------------------------------------
        rr = min(max(risk_reward_ratio / 3.0, 0.0), 1.0)
        score += rr * self._config.risk_reward_weight

        if risk_reward_ratio >= 2.0:
            quality.add_reason(QualityReason.EXCELLENT_RISK_REWARD)
        else:
            quality.add_reason(QualityReason.POOR_RISK_REWARD)

        # ---------------------------------------------
        # Final score
        # ---------------------------------------------
        quality.score = round(score, 2)
        quality.confidence = max(rc, sc)

        if score >= 90:
            quality.level = QualityLevel.EXCELLENT
        elif score >= 75:
            quality.level = QualityLevel.HIGH
        elif score >= 60:
            quality.level = QualityLevel.MEDIUM
        elif score >= 40:
            quality.level = QualityLevel.LOW
        else:
            quality.level = QualityLevel.REJECTED

        return quality