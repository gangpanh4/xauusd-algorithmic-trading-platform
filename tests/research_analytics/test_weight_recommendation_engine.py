from __future__ import annotations

from datetime import UTC
from datetime import datetime

import pytest

from core.feature_engineering.models import (
    Feature,
    FeatureVector,
)
from core.research_analytics.models import (
    TradeAnalytics,
)
from core.research_analytics.storage import (
    ResearchStorage,
)
from core.research_analytics.weight_recommendation_engine import (
    WeightRecommendationEngine,
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
    Create a TradeAnalytics object for testing.
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


def test_recommendations_generated() -> None:
    """
    Recommendations should be generated for every feature.
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
            result="LOSS",
            bos=0.30,
            liquidity=0.60,
        )
    )

    engine = WeightRecommendationEngine(
        storage,
    )

    recommendations = engine.analyze()

    assert len(recommendations) == 2

    recommendation_map = {
        recommendation.feature_name: recommendation
        for recommendation in recommendations
    }

    bos = recommendation_map["bos_strength"]

    assert bos.current_weight == pytest.approx(1.0)
    assert bos.recommended_weight == pytest.approx(0.60)
    assert bos.confidence == pytest.approx(0.60)

    liquidity = recommendation_map["liquidity_quality"]

    assert liquidity.current_weight == pytest.approx(1.0)
    assert liquidity.recommended_weight == pytest.approx(0.20)
    assert liquidity.confidence == pytest.approx(0.20)


def test_empty_storage_returns_empty_list() -> None:
    """
    Empty storage should produce no recommendations.
    """

    storage = ResearchStorage()

    engine = WeightRecommendationEngine(
        storage,
    )

    assert engine.analyze() == []


def test_sorted_by_confidence() -> None:
    """
    Recommendations should be sorted by confidence.
    """

    storage = ResearchStorage()

    storage.add_trade(
        make_trade(
            result="WIN",
            bos=0.95,
            liquidity=0.55,
        )
    )

    storage.add_trade(
        make_trade(
            result="LOSS",
            bos=0.20,
            liquidity=0.45,
        )
    )

    recommendations = WeightRecommendationEngine(
        storage,
    ).analyze()

    assert recommendations[0].confidence >= recommendations[1].confidence