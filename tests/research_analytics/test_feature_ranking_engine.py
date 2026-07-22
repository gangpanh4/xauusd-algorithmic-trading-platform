from __future__ import annotations

import pytest
from datetime import UTC
from datetime import datetime

from core.feature_engineering.models import (
    Feature,
    FeatureVector,
)
from core.research_analytics.feature_ranking_engine import (
    FeatureRankingEngine,
)
from core.research_analytics.models import (
    TradeAnalytics,
)
from core.research_analytics.storage import (
    ResearchStorage,
)
from core.signal_generator.models import (
    SignalDirection,
)


def make_trade(
    *,
    result: str,
    bos: float,
    liquidity: float,
) -> TradeAnalytics:
    """
    Create a TradeAnalytics object containing
    two engineered features.
    """

    features = FeatureVector()

    features.add(
        Feature(
            name="bos_strength",
            value=bos,
            family="structure",
        )
    )

    features.add(
        Feature(
            name="liquidity_quality",
            value=liquidity,
            family="liquidity",
        )
    )

    return TradeAnalytics(
        timestamp=datetime.now(UTC),
        direction=SignalDirection.BUY,
        regime="TRENDING_BULL",
        result=result,
        profit=1.0,
        probability=0.90,
        confidence=0.90,
        features=features,
    )


def test_feature_ranking() -> None:
    """
    Rankings should compute averages correctly.
    """

    storage = ResearchStorage()

    storage.add_trade(
        make_trade(
            result="WIN",
            bos=0.90,
            liquidity=0.80,
        )
    )

    storage.add_trade(
        make_trade(
            result="WIN",
            bos=0.70,
            liquidity=0.60,
        )
    )

    storage.add_trade(
        make_trade(
            result="LOSS",
            bos=0.20,
            liquidity=0.40,
        )
    )

    engine = FeatureRankingEngine(storage)

    rankings = engine.analyze()

    assert len(rankings) == 2

    ranking = {
        r.feature_name: r
        for r in rankings
    }

    assert ranking[
        "bos_strength"
    ].winner_average == pytest.approx(0.80)

    assert ranking[
        "bos_strength"
    ].loser_average == pytest.approx(0.20)

    assert ranking[
        "bos_strength"
    ].gap == pytest.approx(0.60)

    assert ranking[
        "liquidity_quality"
    ].winner_average == pytest.approx(0.70)

    assert ranking[
        "liquidity_quality"
    ].loser_average == pytest.approx(0.40)

    assert ranking[
        "liquidity_quality"
    ].gap == pytest.approx(0.30)


def test_empty_storage() -> None:
    """
    Empty storage should produce
    an empty ranking list.
    """

    storage = ResearchStorage()

    engine = FeatureRankingEngine(storage)

    assert engine.analyze() == []