"""
Tests for the Decision Engine.

These tests verify baseline correctness of the
Decision Engine before research-driven
decision improvements are introduced.
"""

from core.confluence_engine.models import ConfluenceResult
from core.decision_engine.engine import DecisionEngine
from core.decision_engine.models import (
    DecisionResult,
    DecisionType,
)
from core.probability_engine.models import ProbabilityResult
from core.regime_detector.models import (
    MarketRegime,
    RegimeLabel,
)


def create_regime(
    label: RegimeLabel = RegimeLabel.TRENDING_BULL,
    confidence: float = 0.8,
) -> MarketRegime:
    return MarketRegime(
        primary_regime=label,
        confidence=confidence,
    )


def create_probability(
    probability: float = 0.8,
    confidence: float = 0.8,
) -> ProbabilityResult:
    return ProbabilityResult(
        probability=probability,
        confidence=confidence,
        accepted=True,
    )


def create_confluence(
    confidence: float = 0.8,
) -> ConfluenceResult:
    return ConfluenceResult(
        score=confidence,
        maximum_score=1.0,
        approved=True,
        confidence=confidence,
    )


def test_returns_decision_result() -> None:
    """
    evaluate() should always return a DecisionResult.
    """

    engine = DecisionEngine()

    result = engine.evaluate(
        regime=create_regime(),
        probability=create_probability(),
    )

    assert isinstance(result, DecisionResult)


def test_probability_input_is_used() -> None:
    """
    ProbabilityResult should drive the confluence score
    when supplied.
    """

    engine = DecisionEngine()

    result = engine.evaluate(
        regime=create_regime(),
        probability=create_probability(probability=0.75),
    )

    assert result.confluence_score == 0.75


def test_confluence_fallback_is_used() -> None:
    """
    Legacy ConfluenceResult should still be supported.
    """

    engine = DecisionEngine()

    result = engine.evaluate(
        regime=create_regime(),
        confluence=create_confluence(confidence=0.65),
    )

    assert result.confluence_score == 0.65


def test_decision_score_is_normalized() -> None:
    """
    Decision score should remain inside [0, 1].
    """

    engine = DecisionEngine()

    result = engine.evaluate(
        regime=create_regime(),
        probability=create_probability(),
    )

    assert 0.0 <= result.decision_score <= 1.0


def test_confidence_matches_decision_score() -> None:
    """
    Current implementation exposes decision score
    as confidence.
    """

    engine = DecisionEngine()

    result = engine.evaluate(
        regime=create_regime(),
        probability=create_probability(),
    )

    assert result.confidence == result.decision_score


def test_buy_decision_when_threshold_passes() -> None:
    """
    Bullish regime above threshold should produce BUY.
    """

    engine = DecisionEngine()

    result = engine.evaluate(
        regime=create_regime(
            RegimeLabel.TRENDING_BULL,
            confidence=1.0,
        ),
        probability=create_probability(
            probability=1.0,
            confidence=1.0,
        ),
    )

    assert result.decision == DecisionType.BUY
    assert result.approved


def test_hold_when_score_below_threshold() -> None:
    """
    Low scores should produce HOLD.
    """

    engine = DecisionEngine()

    result = engine.evaluate(
        regime=create_regime(
            confidence=0.0,
        ),
        probability=create_probability(
            probability=0.0,
            confidence=0.0,
        ),
    )

    assert result.decision == DecisionType.HOLD
    assert not result.approved


def test_sell_decision_when_bearish() -> None:
    """
    Bearish regime above threshold should produce SELL.
    """

    engine = DecisionEngine()

    result = engine.evaluate(
        regime=create_regime(
            RegimeLabel.TRENDING_BEAR,
            confidence=1.0,
        ),
        probability=create_probability(
            probability=1.0,
            confidence=1.0,
        ),
    )

    assert result.decision == DecisionType.SELL
    assert result.approved