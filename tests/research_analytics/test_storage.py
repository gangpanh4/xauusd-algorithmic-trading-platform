from __future__ import annotations

from datetime import UTC
from datetime import datetime

from core.feature_engineering.models import (
    FeatureVector,
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


def make_trade() -> TradeAnalytics:
    """
    Create a sample TradeAnalytics object for testing.
    """

    return TradeAnalytics(
        timestamp=datetime.now(UTC),
        direction=SignalDirection.BUY,
        regime="TRENDING_BULL",
        result="WIN",
        profit=2.50,
        probability=0.90,
        confidence=0.88,
        features=FeatureVector(),
    )


def test_add_trade() -> None:
    """
    A trade should be stored successfully.
    """

    storage = ResearchStorage()

    storage.add_trade(
        make_trade(),
    )

    assert storage.total_trades == 1


def test_get_trades_returns_tuple() -> None:
    """
    Stored trades should be returned as an immutable tuple.
    """

    storage = ResearchStorage()

    trade = make_trade()

    storage.add_trade(
        trade,
    )

    trades = storage.get_trades()

    assert isinstance(
        trades,
        tuple,
    )

    assert len(trades) == 1

    assert trades[0] == trade


def test_clear_storage() -> None:
    """
    Clearing the storage should remove all trades.
    """

    storage = ResearchStorage()

    storage.add_trade(
        make_trade(),
    )

    storage.clear()

    assert storage.total_trades == 0
    assert storage.get_trades() == ()


def test_total_trades() -> None:
    """
    The total_trades property should reflect
    the number of stored trades.
    """

    storage = ResearchStorage()

    assert storage.total_trades == 0

    storage.add_trade(
        make_trade(),
    )

    storage.add_trade(
        make_trade(),
    )

    assert storage.total_trades == 2