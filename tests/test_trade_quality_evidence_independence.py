from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.feature_engineering.models import Feature, FeatureVector
from core.market_structure.measurements import MarketStructureMeasurements
from core.market_structure.models import MarketStructureResult
from core.probability_engine.models import ProbabilityResult
from core.trade_quality.evidence import TradeQualityEvidenceBuilder


def _structure(confidence: float = 0.8) -> MarketStructureResult:
    return MarketStructureResult(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        last_swing=None,
        last_bos=None,
        last_choch=None,
        last_liquidity=None,
        current_trend=None,
        structure_confidence=confidence,
        measurements=MarketStructureMeasurements(),
    )


def _probability(confidence: float = 0.99) -> ProbabilityResult:
    return ProbabilityResult(probability=0.9, confidence=confidence, accepted=True)


def test_missing_market_evidence_does_not_copy_probability_confidence() -> None:
    evidence = TradeQualityEvidenceBuilder().build(
        market_structure=_structure(),
        feature_vector=FeatureVector(),
        probability=_probability(0.99),
    )

    assert evidence.trend_score == pytest.approx(8.0)
    assert evidence.momentum_score == pytest.approx(5.0)
    assert evidence.volatility_score == pytest.approx(5.0)
    assert evidence.risk_reward_ratio == pytest.approx(2.0)


def test_probability_confidence_cannot_change_independent_scores() -> None:
    builder = TradeQualityEvidenceBuilder()
    low = builder.build(
        market_structure=_structure(),
        feature_vector=FeatureVector(),
        probability=_probability(0.01),
    )
    high = builder.build(
        market_structure=_structure(),
        feature_vector=FeatureVector(),
        probability=_probability(0.99),
    )

    assert low == high


def test_named_and_family_features_are_confidence_weighted() -> None:
    vector = FeatureVector(
        features=[
            Feature("momentum", 0.8, confidence=0.5, normalized=True),
            Feature(
                "atr_percentile",
                0.6,
                confidence=1.0,
                normalized=True,
                family="volatility",
            ),
        ]
    )

    evidence = TradeQualityEvidenceBuilder().build(
        market_structure=_structure(),
        feature_vector=vector,
        probability=_probability(),
    )

    assert evidence.momentum_score == pytest.approx(4.0)
    assert evidence.volatility_score == pytest.approx(6.0)


def test_family_features_are_averaged_without_duplicate_counting() -> None:
    vector = FeatureVector(
        features=[
            Feature("momentum", 0.8, confidence=1.0, family="momentum"),
            Feature("impulse", 0.4, confidence=1.0, family="momentum"),
        ]
    )

    evidence = TradeQualityEvidenceBuilder().build(
        market_structure=_structure(),
        feature_vector=vector,
        probability=_probability(),
    )

    assert evidence.momentum_score == pytest.approx(6.0)


def test_explicit_risk_reward_ratio_overrides_planned_fallback() -> None:
    evidence = TradeQualityEvidenceBuilder(
        planned_risk_reward_ratio=2.0,
    ).build(
        market_structure=_structure(),
        feature_vector=FeatureVector(),
        probability=_probability(),
        risk_reward_ratio=2.75,
    )

    assert evidence.risk_reward_ratio == pytest.approx(2.75)


def test_price_geometry_calculates_actual_risk_reward() -> None:
    evidence = TradeQualityEvidenceBuilder().build(
        market_structure=_structure(),
        feature_vector=FeatureVector(),
        probability=_probability(),
        entry_price=2400.0,
        stop_loss_price=2395.0,
        take_profit_price=2412.5,
    )

    assert evidence.risk_reward_ratio == pytest.approx(2.5)


def test_invalid_or_ambiguous_geometry_fails_closed() -> None:
    builder = TradeQualityEvidenceBuilder()
    common = dict(
        market_structure=_structure(),
        feature_vector=FeatureVector(),
        probability=_probability(),
    )

    with pytest.raises(ValueError):
        builder.build(**common, entry_price=2400.0)

    with pytest.raises(ValueError):
        builder.build(
            **common,
            risk_reward_ratio=2.0,
            entry_price=2400.0,
            stop_loss_price=2395.0,
            take_profit_price=2410.0,
        )

    with pytest.raises(ValueError):
        builder.build(
            **common,
            entry_price=2400.0,
            stop_loss_price=2395.0,
            take_profit_price=2390.0,
        )


def test_configuration_and_non_finite_features_fail_closed() -> None:
    with pytest.raises(ValueError):
        TradeQualityEvidenceBuilder(neutral_missing_score=11.0)
    with pytest.raises(ValueError):
        TradeQualityEvidenceBuilder(planned_risk_reward_ratio=0.0)

    vector = FeatureVector(
        features=[Feature("momentum", float("nan"), confidence=1.0)]
    )
    with pytest.raises(ValueError):
        TradeQualityEvidenceBuilder().build(
            market_structure=_structure(),
            feature_vector=vector,
            probability=_probability(),
        )
