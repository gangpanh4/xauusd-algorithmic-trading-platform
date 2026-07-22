from __future__ import annotations

import math

import pytest

from core.trade_quality.models import QualityLevel
from core.trade_quality.scorer import (
    TradeQualityScorer,
    TradeQualityScorerConfig,
)


def test_component_contributions_sum_to_score() -> None:
    quality = TradeQualityScorer().score(
        trend_score=8.0,
        momentum_score=6.0,
        volatility_score=4.0,
        regime_confidence=0.85,
        signal_confidence=0.75,
        risk_reward_ratio=2.0,
    )

    components = quality.metadata["components"]
    total = sum(
        component["contribution"]
        for component in components.values()
    )

    assert quality.score == round(total, 2)
    assert quality.metadata["weight_total"] == 100.0


def test_close_confidences_retain_stronger_value() -> None:
    quality = TradeQualityScorer().score(
        trend_score=5.0,
        momentum_score=5.0,
        volatility_score=5.0,
        regime_confidence=0.85,
        signal_confidence=0.80,
        risk_reward_ratio=2.0,
    )

    assert quality.confidence == 0.85


def test_divergent_confidences_are_capped_by_weaker_evidence() -> None:
    quality = TradeQualityScorer().score(
        trend_score=5.0,
        momentum_score=5.0,
        volatility_score=5.0,
        regime_confidence=0.95,
        signal_confidence=0.30,
        risk_reward_ratio=2.0,
    )

    assert quality.confidence == 0.35
    assert quality.metadata["confidence_method"] == (
        "WEAKER_EVIDENCE_PLUS_TOLERANCE_CAP"
    )


def test_score_scale_and_levels_remain_compatible() -> None:
    quality = TradeQualityScorer().score(
        trend_score=10.0,
        momentum_score=10.0,
        volatility_score=10.0,
        regime_confidence=1.0,
        signal_confidence=1.0,
        risk_reward_ratio=3.0,
    )

    assert quality.score == 100.0
    assert quality.level is QualityLevel.EXCELLENT


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("trend_weight", -1.0),
        ("momentum_weight", math.inf),
        ("risk_reward_maximum", 0.0),
        ("confidence_disagreement_tolerance", 1.1),
    ],
)
def test_invalid_config_fails_closed(field: str, value: float) -> None:
    kwargs = {field: value}
    with pytest.raises((TypeError, ValueError)):
        TradeQualityScorerConfig(**kwargs)


def test_weights_must_sum_to_one_hundred() -> None:
    with pytest.raises(ValueError, match="sum to 100"):
        TradeQualityScorerConfig(trend_weight=19.0)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("trend_score", -0.1),
        ("momentum_score", 10.1),
        ("volatility_score", math.nan),
        ("regime_confidence", 1.1),
        ("signal_confidence", -0.1),
        ("risk_reward_ratio", 3.1),
    ],
)
def test_invalid_input_fails_closed(field: str, value: float) -> None:
    values = {
        "trend_score": 5.0,
        "momentum_score": 5.0,
        "volatility_score": 5.0,
        "regime_confidence": 0.8,
        "signal_confidence": 0.8,
        "risk_reward_ratio": 2.0,
    }
    values[field] = value

    with pytest.raises((TypeError, ValueError)):
        TradeQualityScorer().score(**values)
