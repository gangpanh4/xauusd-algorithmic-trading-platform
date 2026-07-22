"""
Signal Generator Scorer.

Computes the overall strength of a trading signal.
"""

from __future__ import annotations

from math import isfinite

from .config import SignalScorerConfig
from .context import SignalContext
from .models import SignalScore


class SignalScorer:
    """
    Compute a normalized composite signal score.

    Each available upstream score is normalized to the range
    ``[0.0, 1.0]`` before its configured weight is applied.
    """

    def __init__(
        self,
        config: SignalScorerConfig | None = None,
    ) -> None:
        self.config = config or SignalScorerConfig()

    def score(
        self,
        context: SignalContext,
    ) -> SignalScore:
        """Return the weighted composite score for ``context``."""

        probability = (
            self._probability_score(context)
            * self.config.probability_weight
        )

        trade_quality = (
            self._trade_quality_score(context)
            * self.config.trade_quality_weight
        )

        decision = (
            self._decision_score(context)
            * self.config.decision_weight
        )

        confluence = (
            self._confluence_score(context)
            * self.config.confluence_weight
        )

        regime = (
            self._regime_score(context)
            * self.config.regime_weight
        )

        total = (
            probability
            + trade_quality
            + decision
            + confluence
            + regime
        )

        return SignalScore(value=total)

    def _probability_score(
        self,
        context: SignalContext,
    ) -> float:
        if context.probability is None:
            return 0.0

        return self._normalize_unit_interval(
            context.probability.probability,
            source="probability.probability",
        )

    def _trade_quality_score(
        self,
        context: SignalContext,
    ) -> float:
        if context.trade_quality is None:
            return 0.0

        return self._normalize_unit_interval(
            context.trade_quality.score / 100.0,
            source="trade_quality.score",
        )

    def _decision_score(
        self,
        context: SignalContext,
    ) -> float:
        if context.decision is None:
            return 0.0

        return self._normalize_unit_interval(
            context.decision.decision_score,
            source="decision.decision_score",
        )

    def _confluence_score(
        self,
        context: SignalContext,
    ) -> float:
        if context.confluence is None:
            return 0.0

        return self._normalize_unit_interval(
            context.confluence.confidence,
            source="confluence.confidence",
        )

    def _regime_score(
        self,
        context: SignalContext,
    ) -> float:
        return self._normalize_unit_interval(
            context.regime.confidence,
            source="regime.confidence",
        )

    @staticmethod
    def _normalize_unit_interval(
        value: float,
        *,
        source: str,
    ) -> float:
        """Validate and clamp one normalized source score."""

        if not isfinite(value):
            raise ValueError(f"{source} must be finite.")

        return max(0.0, min(1.0, value))
