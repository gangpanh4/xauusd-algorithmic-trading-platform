"""
Decision Engine.
"""

from __future__ import annotations

from datetime import UTC, datetime
from math import isfinite
from numbers import Real

from core.confluence_engine.models import ConfluenceResult
from core.probability_engine.models import ProbabilityResult
from core.regime_detector.models import MarketRegime, RegimeLabel

from .config import DecisionEngineConfig
from .models import DecisionResult, DecisionType


class DecisionEngine:
    """
    Convert directional regime and supporting evidence into a decision.

    The regime owns trade direction. Probability and confluence are independent
    supporting evidence sources; when both are available neither source may
    silently replace the other.

    The engine does not generate signals, size positions, or execute orders.
    """

    def __init__(
        self,
        config: DecisionEngineConfig | None = None,
    ) -> None:
        self.config = config if config is not None else DecisionEngineConfig()
        self._validate_config(self.config)

    def evaluate(
        self,
        *,
        regime: MarketRegime,
        confluence: ConfluenceResult | None = None,
        probability: ProbabilityResult | None = None,
        timestamp: datetime | None = None,
    ) -> DecisionResult:
        """Evaluate the current market and produce a decision."""

        if not isinstance(regime, MarketRegime):
            raise TypeError("regime must be a MarketRegime")
        if confluence is not None and not isinstance(confluence, ConfluenceResult):
            raise TypeError("confluence must be a ConfluenceResult or None")
        if probability is not None and not isinstance(probability, ProbabilityResult):
            raise TypeError("probability must be a ProbabilityResult or None")

        regime_score = self._evaluate_regime(regime)
        probability_score = self._evaluate_probability(probability)
        confluence_score = self._evaluate_confluence(confluence)
        supporting_evidence_score = self._combine_supporting_evidence(
            probability_score=probability_score,
            confluence_score=confluence_score,
        )

        decision_score = self._compute_decision_score(
            regime_score=regime_score,
            supporting_evidence_score=supporting_evidence_score,
        )

        return self._make_decision(
            regime=regime,
            decision_score=decision_score,
            regime_score=regime_score,
            supporting_evidence_score=supporting_evidence_score,
            timestamp=timestamp,
        )

    def _evaluate_regime(self, regime: MarketRegime) -> float:
        """Return validated normalized regime confidence."""

        if not isinstance(regime.primary_regime, RegimeLabel):
            raise TypeError("regime.primary_regime must be a RegimeLabel")
        return self._validate_normalized_score(
            regime.confidence,
            name="regime confidence",
        )

    def _evaluate_probability(
        self,
        probability: ProbabilityResult | None,
    ) -> float | None:
        """Return validated probability evidence when available."""

        if probability is None:
            return None
        return self._validate_normalized_score(
            probability.probability,
            name="probability",
        )

    def _evaluate_confluence(
        self,
        confluence: ConfluenceResult | None,
    ) -> float | None:
        """Return validated confluence confidence when available."""

        if confluence is None:
            return None
        return self._validate_normalized_score(
            confluence.confidence,
            name="confluence confidence",
        )

    @staticmethod
    def _combine_supporting_evidence(
        *,
        probability_score: float | None,
        confluence_score: float | None,
    ) -> float:
        """
        Combine independent supporting evidence without double counting.

        With both sources present, each contributes equally. A single available
        source remains a backward-compatible fallback. With no supporting
        evidence, the score fails closed at zero.
        """

        available_scores = tuple(
            score
            for score in (probability_score, confluence_score)
            if score is not None
        )
        if not available_scores:
            return 0.0
        return sum(available_scores) / len(available_scores)

    def _compute_decision_score(
        self,
        *,
        regime_score: float,
        supporting_evidence_score: float,
    ) -> float:
        """Combine regime and supporting evidence using configured weights."""

        total_weight = self.config.regime_weight + self.config.confluence_weight
        return (
            regime_score * self.config.regime_weight
            + supporting_evidence_score * self.config.confluence_weight
        ) / total_weight

    def _make_decision(
        self,
        *,
        regime: MarketRegime,
        decision_score: float,
        regime_score: float,
        supporting_evidence_score: float,
        timestamp: datetime | None = None,
    ) -> DecisionResult:
        """Convert a validated score into BUY, SELL, or HOLD."""

        if (
            regime.primary_regime is RegimeLabel.TRENDING_BULL
            and decision_score >= self.config.minimum_decision_score
        ):
            decision = DecisionType.BUY
        elif (
            regime.primary_regime is RegimeLabel.TRENDING_BEAR
            and decision_score >= self.config.minimum_decision_score
        ):
            decision = DecisionType.SELL
        else:
            decision = DecisionType.HOLD

        result_timestamp = (
            datetime.now(UTC) if timestamp is None else timestamp
        )
        return DecisionResult(
            timestamp=result_timestamp,
            decision=decision,
            approved=decision is not DecisionType.HOLD,
            confidence=decision_score,
            decision_score=decision_score,
            regime_confidence=regime_score,
            # Backward-compatible field: it now contains the combined
            # probability/confluence supporting-evidence score.
            confluence_score=supporting_evidence_score,
        )

    @classmethod
    def _validate_config(cls, config: DecisionEngineConfig) -> None:
        """Validate the mutable legacy configuration at engine construction."""

        if not isinstance(config, DecisionEngineConfig):
            raise TypeError("config must be a DecisionEngineConfig")

        minimum_score = cls._validate_normalized_score(
            config.minimum_decision_score,
            name="minimum_decision_score",
        )
        regime_weight = cls._validate_weight(
            config.regime_weight,
            name="regime_weight",
        )
        confluence_weight = cls._validate_weight(
            config.confluence_weight,
            name="confluence_weight",
        )
        if regime_weight + confluence_weight <= 0.0:
            raise ValueError("decision weights must have a positive total")

        # Retain the reference so static analysis does not treat validation as
        # unused and make the normalized contract explicit.
        _ = minimum_score

    @staticmethod
    def _validate_weight(value: float, *, name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError(f"{name} must be a real number")
        normalized = float(value)
        if not isfinite(normalized) or normalized < 0.0:
            raise ValueError(f"{name} must be finite and non-negative")
        return normalized

    @staticmethod
    def _validate_normalized_score(value: float, *, name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError(f"{name} must be a real number")
        normalized = float(value)
        if not isfinite(normalized) or not 0.0 <= normalized <= 1.0:
            raise ValueError(f"{name} must be finite and within [0, 1]")
        return normalized
