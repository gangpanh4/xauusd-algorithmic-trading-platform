from __future__ import annotations

from datetime import UTC
from datetime import datetime

import pytest

from core.feature_engineering.models import (
    FeatureVector,
)
from core.research_analytics.engine import (
    ResearchAnalyticsEngine,
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
    result: str = "WIN",
    profit: float = 1.0,
    probability: float = 0.80,
    confidence: float = 0.90,
) -> TradeAnalytics:
    """
    Create a TradeAnalytics object for testing.
    """

    return TradeAnalytics(
        timestamp=datetime.now(UTC),
        direction=SignalDirection.BUY,
        regime="TRENDING_BULL",
        result=result,
        profit=profit,
        probability=probability,
        confidence=confidence,
        features=FeatureVector(),
    )


def test_total_trades() -> None:
    storage = ResearchStorage()

    storage.add_trade(make_trade())
    storage.add_trade(make_trade())

    engine = ResearchAnalyticsEngine(storage)

    assert engine.total_trades == 2


def test_winning_trades() -> None:
    storage = ResearchStorage()

    storage.add_trade(make_trade(result="WIN"))
    storage.add_trade(make_trade(result="LOSS"))
    storage.add_trade(make_trade(result="WIN"))

    engine = ResearchAnalyticsEngine(storage)

    assert engine.winning_trades == 2


def test_losing_trades() -> None:
    storage = ResearchStorage()

    storage.add_trade(make_trade(result="LOSS"))
    storage.add_trade(make_trade(result="LOSS"))
    storage.add_trade(make_trade(result="WIN"))

    engine = ResearchAnalyticsEngine(storage)

    assert engine.losing_trades == 2


def test_average_probability() -> None:
    storage = ResearchStorage()

    storage.add_trade(make_trade(probability=0.80))
    storage.add_trade(make_trade(probability=1.00))

    engine = ResearchAnalyticsEngine(storage)

    assert engine.average_probability == pytest.approx(0.90)


def test_average_confidence() -> None:
    storage = ResearchStorage()

    storage.add_trade(make_trade(confidence=0.80))
    storage.add_trade(make_trade(confidence=1.00))

    engine = ResearchAnalyticsEngine(storage)

    assert engine.average_confidence == pytest.approx(0.90)


def test_average_profit() -> None:
    storage = ResearchStorage()

    storage.add_trade(make_trade(profit=2.0))
    storage.add_trade(make_trade(profit=4.0))

    engine = ResearchAnalyticsEngine(storage)

    assert engine.average_profit == pytest.approx(3.0)


def test_win_rate() -> None:
    storage = ResearchStorage()

    storage.add_trade(make_trade(result="WIN"))
    storage.add_trade(make_trade(result="WIN"))
    storage.add_trade(make_trade(result="LOSS"))
    storage.add_trade(make_trade(result="LOSS"))

    engine = ResearchAnalyticsEngine(storage)

    assert engine.win_rate == pytest.approx(0.5)


def test_empty_storage_returns_zero_values() -> None:
    storage = ResearchStorage()

    engine = ResearchAnalyticsEngine(storage)

    assert engine.total_trades == 0
    assert engine.winning_trades == 0
    assert engine.losing_trades == 0
    assert engine.breakeven_trades == 0
    assert engine.average_profit == 0.0
    assert engine.average_probability == 0.0
    assert engine.average_confidence == 0.0
    assert engine.win_rate == 0.0