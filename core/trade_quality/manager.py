"""
Trade Quality Manager.

Coordinates scoring and filtering of trading opportunities.
"""

from __future__ import annotations

from .filters import (
    TradeQualityFilter,
    TradeQualityFilterConfig,
)
from .models import TradeQuality
from .scorer import (
    TradeQualityScorer,
    TradeQualityScorerConfig,
)


class TradeQualityManager:
    """
    High-level interface for evaluating trade quality.
    """

    def __init__(
        self,
        scorer: TradeQualityScorer | None = None,
        trade_filter: TradeQualityFilter | None = None,
    ) -> None:

        self._scorer = scorer or TradeQualityScorer(
            TradeQualityScorerConfig()
        )

        self._filter = trade_filter or TradeQualityFilter(
            TradeQualityFilterConfig()
        )

    @property
    def scorer(self) -> TradeQualityScorer:
        return self._scorer

    @property
    def filter(
        self,
    ) -> TradeQualityFilter:
        """
        Return the configured trade quality filter.
        """

        return self._filter

    @property
    def trade_filter(
        self,
    ) -> TradeQualityFilter:
        """
        Backward-compatible alias.
        """

        return self.filter

    def evaluate(
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
        Evaluate a trading opportunity.

        Returns
        -------
        TradeQuality
        """

        quality = self._scorer.score(
            trend_score=trend_score,
            momentum_score=momentum_score,
            volatility_score=volatility_score,
            regime_confidence=regime_confidence,
            signal_confidence=signal_confidence,
            risk_reward_ratio=risk_reward_ratio,
        )

        return self._filter.apply(quality)