from __future__ import annotations

import math

import pytest

from core.confluence_engine.models import ConfluenceResult
from core.decision_engine.config import DecisionEngineConfig
from core.decision_engine.engine import DecisionEngine
from core.decision_engine.models import DecisionType
from core.probability_engine.models import ProbabilityResult
from core.regime_detector.models import MarketRegime, RegimeLabel


def _regime(
    label: RegimeLabel = RegimeLabel.TRENDING_BULL,
    confidence: float = 0.8,
) -> MarketRegime:
    return MarketRegime(primary_regime=label, confidence=confidence)


def _probability(value: float) -> ProbabilityResult:
    return ProbabilityResult(probability=value, confidence=value, accepted=True)


def _confluence(value: float) -> ConfluenceResult:
    return ConfluenceResult(
        score=value * 100.0,
        maximum_score=100.0,
        confidence=value,
        approved=value >= 0.4,
    )


def test_probability_and_confluence_are_both_used() -> None:
    result = DecisionEngine().evaluate(
        regime=_regime(confidence=0.8),
        probability=_probability(0.8),
        confluence=_confluence(0.4),
    )

    assert result.confluence_score == pytest.approx(0.6)
    assert result.decision_score == pytest.approx(0.7)
    assert result.decision is DecisionType.BUY


def test_probability_only_remains_supported() -> None:
    result = DecisionEngine().evaluate(
        regime=_regime(confidence=0.8),
        probability=_probability(0.6),
    )

    assert result.confluence_score == pytest.approx(0.6)
    assert result.decision_score == pytest.approx(0.7)


def test_confluence_only_remains_supported() -> None:
    result = DecisionEngine().evaluate(
        regime=_regime(confidence=0.8),
        confluence=_confluence(0.6),
    )

    assert result.confluence_score == pytest.approx(0.6)


def test_missing_supporting_evidence_fails_closed() -> None:
    result = DecisionEngine().evaluate(regime=_regime(confidence=1.0))

    assert result.confluence_score == 0.0
    assert result.decision is DecisionType.HOLD
    assert not result.approved


def test_non_directional_regime_cannot_trade() -> None:
    result = DecisionEngine().evaluate(
        regime=_regime(RegimeLabel.RANGING, confidence=1.0),
        probability=_probability(1.0),
        confluence=_confluence(1.0),
    )

    assert result.decision is DecisionType.HOLD


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("minimum_decision_score", math.nan),
        ("minimum_decision_score", 1.1),
        ("regime_weight", -0.1),
        ("confluence_weight", math.inf),
    ],
)
def test_invalid_config_fails_closed(field: str, value: float) -> None:
    with pytest.raises((TypeError, ValueError)):
        DecisionEngine(DecisionEngineConfig(**{field: value}))


def test_zero_total_weight_fails_closed() -> None:
    with pytest.raises(ValueError, match="positive total"):
        DecisionEngine(
            DecisionEngineConfig(regime_weight=0.0, confluence_weight=0.0)
        )


@pytest.mark.parametrize(
    ("input_name", "value"),
    [
        ("regime", 1.1),
        ("probability", -0.1),
        ("confluence", math.inf),
    ],
)
def test_invalid_evidence_fails_closed(input_name: str, value: float) -> None:
    regime = _regime(confidence=value if input_name == "regime" else 0.8)
    probability = _probability(value if input_name == "probability" else 0.8)
    confluence = _confluence(value if input_name == "confluence" else 0.8)

    with pytest.raises((TypeError, ValueError)):
        DecisionEngine().evaluate(
            regime=regime,
            probability=probability,
            confluence=confluence,
        )
