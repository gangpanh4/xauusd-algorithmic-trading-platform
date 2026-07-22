from __future__ import annotations

from datetime import UTC
from datetime import datetime

import pytest

from core.feature_engineering.models import (
    Feature,
    FeatureVector,
)
from core.research_analytics.feature_statistics_engine import (
    FeatureStatisticsEngine,
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
    Create a trade containing engineered features.
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


def test_statistics() -> None:
    """
    Statistics should be computed correctly.
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

    engine = FeatureStatisticsEngine(storage)

    statistics = {
        s.feature_name: s
        for s in engine.analyze()
    }

    bos = statistics["bos_strength"]

    assert bos.count == 3
    assert bos.minimum == pytest.approx(0.20)
    assert bos.maximum == pytest.approx(0.90)
    assert bos.mean == pytest.approx((0.90 + 0.70 + 0.20) / 3)
    assert bos.winner_mean == pytest.approx(0.80)
    assert bos.loser_mean == pytest.approx(0.20)
    assert bos.gap == pytest.approx(0.60)

    liquidity = statistics["liquidity_quality"]

    assert liquidity.count == 3
    assert liquidity.minimum == pytest.approx(0.40)
    assert liquidity.maximum == pytest.approx(0.80)
    assert liquidity.mean == pytest.approx((0.80 + 0.60 + 0.40) / 3)
    assert liquidity.winner_mean == pytest.approx(0.70)
    assert liquidity.loser_mean == pytest.approx(0.40)
    assert liquidity.gap == pytest.approx(0.30)


def test_empty_storage() -> None:
    """
    Empty storage should produce no statistics.
    """

    storage = ResearchStorage()

    engine = FeatureStatisticsEngine(storage)

    assert engine.analyze() == []