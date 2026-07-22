"""Tests for explicit SignalGatekeeper approval contracts."""

from __future__ import annotations

from core.decision_engine.models import DecisionResult, DecisionType
from core.probability_engine.models import ProbabilityResult
from core.regime_detector.models import MarketRegime, RegimeLabel
from core.signal_generator.context import SignalContext
from core.signal_generator.gatekeeper import SignalGatekeeper


def _bullish_regime() -> MarketRegime:
    return MarketRegime(
        primary_regime=RegimeLabel.TRENDING_BULL,
        confidence=0.90,
        trend_score=4.0,
        momentum_score=1.0,
        volatility_score=1.0,
        ema_score=1.0,
        choppiness_score=2.0,
        total_score=9.0,
    )


def _approved_decision() -> DecisionResult:
    return DecisionResult(
        decision=DecisionType.BUY,
        approved=True,
        confidence=0.90,
        decision_score=0.90,
        regime_confidence=0.90,
        confluence_score=0.90,
    )


def test_rejects_explicitly_rejected_probability() -> None:
    """A rejected ProbabilityResult must veto an otherwise approved trade."""

    context = SignalContext(
        regime=_bullish_regime(),
        probability=ProbabilityResult(
            probability=0.80,
            confidence=0.40,
            accepted=False,
        ),
        decision=_approved_decision(),
    )

    assert SignalGatekeeper().approve(context) is False


def test_allows_accepted_probability_when_decision_is_approved() -> None:
    """An accepted probability should continue to the existing decision gate."""

    context = SignalContext(
        regime=_bullish_regime(),
        probability=ProbabilityResult(
            probability=0.80,
            confidence=0.80,
            accepted=True,
        ),
        decision=_approved_decision(),
    )

    assert SignalGatekeeper().approve(context) is True


def test_missing_probability_preserves_legacy_behavior() -> None:
    """Legacy callers that omit probability still follow DecisionEngine output."""

    context = SignalContext(
        regime=_bullish_regime(),
        probability=None,
        decision=_approved_decision(),
    )

    assert SignalGatekeeper().approve(context) is True
