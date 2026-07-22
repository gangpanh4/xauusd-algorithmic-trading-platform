"""
Unit tests for the Order Block repository.
"""

from __future__ import annotations

from datetime import datetime, timezone

from core.market_structure.enums import (
    BreakType,
    MarketTrend,
    OrderBlockType,
    SwingType,
)
from core.market_structure.models import (
    BOSEvent,
    SwingPoint,
)
from core.order_block_detector.models import (
    OrderBlock,
)
from core.order_block_detector.repository import (
    OrderBlockRepository,
)


def make_swing() -> SwingPoint:
    return SwingPoint(
        timestamp=datetime.now(timezone.utc),
        index=1,
        price=100.0,
        swing_type=SwingType.LOW,
        confirmation_index=1,
    )


def make_break() -> BOSEvent:
    swing = make_swing()

    return BOSEvent(
        timestamp=datetime.now(timezone.utc),
        break_type=BreakType.BOS,
        direction=MarketTrend.BULLISH,
        break_price=101.0,
        swing_point=swing,
        confirmation_index=2,
    )


def make_order_block() -> OrderBlock:
    swing = make_swing()

    return OrderBlock(
        timestamp=datetime.now(timezone.utc),
        block_type=OrderBlockType.BULLISH,
        top_price=101.0,
        bottom_price=100.0,
        origin_swing=swing,
        trigger_break=make_break(),
        trigger_liquidity=None,
        creation_index=2,
        confirmation_index=3,
    )


def test_repository_starts_empty() -> None:
    """
    Repository should start empty.
    """

    repository = OrderBlockRepository()

    assert repository.count() == 0
    assert repository.get_all() == []


def test_add_order_block() -> None:
    """
    Repository should store an Order Block.
    """

    repository = OrderBlockRepository()

    block = make_order_block()

    repository.add(block)

    assert repository.count() == 1
    assert repository.get_all() == [block]


def test_clear_repository() -> None:
    """
    clear() should remove every Order Block.
    """

    repository = OrderBlockRepository()

    repository.add(make_order_block())

    assert repository.count() == 1

    repository.clear()

    assert repository.count() == 0
    assert repository.get_all() == []