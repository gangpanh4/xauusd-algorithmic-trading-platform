from __future__ import annotations

from datetime import UTC
from datetime import datetime

from core.feature_engineering.models import (
    FeatureVector,
)
from core.research_analytics.models import (
    TradeAnalytics,
)
from core.signal_generator.models import (
    SignalDirection,
)


def test_trade_analytics_creation() -> None:
    """
    TradeAnalytics should correctly store all
    supplied trade information.
    """

    features = FeatureVector()

    analytics = TradeAnalytics(
        timestamp=datetime.now(UTC),
        direction=SignalDirection.BUY,
        regime="TRENDING_BULL",
        result="WIN",
        profit=2.50,
        probability=0.91,
        confidence=0.88,
        features=features,
    )

    assert analytics.direction == SignalDirection.BUY
    assert analytics.regime == "TRENDING_BULL"
    assert analytics.result == "WIN"
    assert analytics.profit == 2.50
    assert analytics.probability == 0.91
    assert analytics.confidence == 0.88
    assert analytics.features is features


def test_trade_analytics_supports_losses() -> None:
    """
    Losing trades should also be represented correctly.
    """

    features = FeatureVector()

    analytics = TradeAnalytics(
        timestamp=datetime.now(UTC),
        direction=SignalDirection.SELL,
        regime="TRENDING_BEAR",
        result="LOSS",
        profit=-1.25,
        probability=0.74,
        confidence=0.81,
        features=features,
    )

    assert analytics.direction == SignalDirection.SELL
    assert analytics.result == "LOSS"
    assert analytics.profit == -1.25
    assert analytics.features is features