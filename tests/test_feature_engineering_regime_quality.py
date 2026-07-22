from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.feature_engineering.config import FeatureEngineeringConfig
from core.feature_engineering.engine import FeatureEngineeringEngine
from core.regime_detector.models import MarketRegime, RegimeLabel


def _regime(
    *,
    label: RegimeLabel = RegimeLabel.TRENDING_BULL,
    confidence: float = 0.8,
    momentum: float = 1.0,
    volatility: float = 2.0,
) -> MarketRegime:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    return MarketRegime(
        primary_regime=label,
        confidence=confidence,
        observation_timestamp=timestamp,
        computation_timestamp=timestamp,
        momentum_score=momentum,
        volatility_score=volatility,
    )


def test_confirmed_regime_emits_independent_normalized_features() -> None:
    engine = FeatureEngineeringEngine()

    vector = engine.process(engine.create_evidence(regime=_regime()))

    momentum = vector.get("momentum_score")
    volatility = vector.get("volatility_score")

    assert momentum is not None
    assert momentum.value == pytest.approx(0.5)
    assert momentum.confidence == pytest.approx(0.8)
    assert momentum.family == "momentum"
    assert momentum.source == "confirmed_regime_detector"

    assert volatility is not None
    assert volatility.value == pytest.approx(1.0)
    assert volatility.confidence == pytest.approx(0.8)
    assert volatility.family == "volatility"


def test_probability_confidence_is_not_an_input() -> None:
    engine = FeatureEngineeringEngine()
    regime = _regime(confidence=0.65, momentum=2.0, volatility=1.0)

    vector = engine.process(engine.create_evidence(regime=regime))

    assert vector.get("momentum_score").value == pytest.approx(1.0)
    assert vector.get("volatility_score").value == pytest.approx(0.5)


def test_unknown_regime_does_not_fabricate_zero_evidence() -> None:
    engine = FeatureEngineeringEngine()

    vector = engine.process(
        engine.create_evidence(regime=_regime(label=RegimeLabel.UNKNOWN))
    )

    assert vector.get("momentum_score") is None
    assert vector.get("volatility_score") is None


def test_zero_scores_from_confirmed_regime_are_real_evidence() -> None:
    engine = FeatureEngineeringEngine()

    vector = engine.process(
        engine.create_evidence(
            regime=_regime(
                label=RegimeLabel.RANGING,
                momentum=0.0,
                volatility=0.0,
            )
        )
    )

    assert vector.get("momentum_score").value == 0.0
    assert vector.get("volatility_score").value == 0.0


def test_minimum_confidence_filters_both_features() -> None:
    engine = FeatureEngineeringEngine(
        FeatureEngineeringConfig(minimum_confidence=0.7)
    )

    vector = engine.process(
        engine.create_evidence(regime=_regime(confidence=0.6))
    )

    assert vector.get("momentum_score") is None
    assert vector.get("volatility_score") is None


@pytest.mark.parametrize("field", ["momentum", "volatility"])
def test_invalid_regime_component_fails_closed(field: str) -> None:
    engine = FeatureEngineeringEngine()
    kwargs = {field: 2.1}

    with pytest.raises(ValueError):
        engine.process(engine.create_evidence(regime=_regime(**kwargs)))


def test_invalid_evidence_type_fails_closed() -> None:
    engine = FeatureEngineeringEngine()

    with pytest.raises(TypeError):
        engine.process(object())  # type: ignore[arg-type]
