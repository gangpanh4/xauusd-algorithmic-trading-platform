"""
Decision Engine.
"""

from __future__ import annotations

from core.confluence_engine.models import (
    ConfluenceResult,
)

from core.probability_engine.models import (
    ProbabilityResult,
)

from core.regime_detector.models import (
    MarketRegime,
    RegimeLabel,
)

from .config import DecisionEngineConfig

from .models import (
    DecisionResult,
    DecisionType,
)


class DecisionEngine:
    """
    Combines market regime and confluence analysis into a
    quantitative trading decision.

    The Decision Engine is responsible only for deciding
    whether the market conditions justify a trade.

    It does not perform signal generation, risk management,
    or order execution.
    """

    def __init__(
        self,
        config: DecisionEngineConfig | None = None,
    ) -> None:
        self.config = (
            config
            if config is not None
            else DecisionEngineConfig()
        )

    def evaluate(
        self,
        *,
        regime: MarketRegime,
        confluence: ConfluenceResult | None = None,
        probability: ProbabilityResult | None = None,
    ) -> DecisionResult:
        """
        Evaluate the current market and produce a decision.
        """

        regime_score = self._evaluate_regime(
            regime,
        )

        if probability is not None:

            confluence_score = probability.probability

        else:

            confluence_score = self._evaluate_confluence(
                confluence,
            )

        decision_score = self._compute_decision_score(
            regime_score=regime_score,
            confluence_score=confluence_score,
        )

        return self._make_decision(
            regime=regime,
            decision_score=decision_score,
            regime_score=regime_score,
            confluence_score=confluence_score,
        )

    def _evaluate_regime(
        self,
        regime: MarketRegime,
    ) -> float:
        """
        Evaluate the market regime.

        Version 2 currently uses the regime confidence
        directly.
        """

        return regime.confidence

    def _evaluate_confluence(
        self,
        confluence: ConfluenceResult | None,
    ) -> float:
        """
        Evaluate confluence quality.

        Version 2 currently uses the normalized
        confluence confidence.
        """

        if confluence is None:
            return 0.0

        return confluence.confidence

    def _compute_decision_score(
        self,
        *,
        regime_score: float,
        confluence_score: float,
    ) -> float:
        """
        Combine regime and confluence into one score.
        """

        total_weight = (
            self.config.regime_weight
            + self.config.confluence_weight
        )

        return (
            (
                regime_score
                * self.config.regime_weight
            )
            + (
                confluence_score
                * self.config.confluence_weight
            )
        ) / total_weight

    def _make_decision(
        self,
        *,
        regime: MarketRegime,
        decision_score: float,
        regime_score: float,
        confluence_score: float,
    ) -> DecisionResult:
        """
        Convert the computed score into a decision.

        Version 2 keeps the policy intentionally simple.
        """

        if (
            regime.primary_regime
            == RegimeLabel.TRENDING_BULL
            and decision_score
            >= self.config.minimum_decision_score
        ):
            decision = DecisionType.BUY

        elif (
            regime.primary_regime
            == RegimeLabel.TRENDING_BEAR
            and decision_score
            >= self.config.minimum_decision_score
        ):
            decision = DecisionType.SELL

        else:
            decision = DecisionType.HOLD

        return DecisionResult(
            decision=decision,
            approved=decision != DecisionType.HOLD,
            confidence=decision_score,
            decision_score=decision_score,
            regime_confidence=regime_score,
            confluence_score=confluence_score,
        )