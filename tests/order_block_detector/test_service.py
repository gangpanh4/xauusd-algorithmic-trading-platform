"""
Unit tests for the Order Block application service.
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
from core.order_block_detector.service import (
    OrderBlockService,
)


def make_swing() -> SwingPoint:
    """
    Create a confirmed swing point.
    """

    return SwingPoint(
        timestamp=datetime.now(timezone.utc),
        index=1,
        price=100.0,
        swing_type=SwingType.LOW,
        confirmation_index=1,
    )


def make_break() -> BOSEvent:
    """
    Create a valid BOS event.
    """

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
    """
    Create a valid Order Block.
    """

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


def test_service_starts_empty() -> None:
    """
    Service should start empty.
    """

    service = OrderBlockService()

    assert service.count() == 0
    assert service.get_all() == []


def test_add_order_block() -> None:
    """
    Adding an Order Block should store it and return analysis.
    """

    service = OrderBlockService()

    block = make_order_block()

    analysis = service.add(block)

    assert analysis.total_score == 1.0

    assert service.count() == 1

    assert service.get_all() == [block]


def test_clear_service() -> None:
    """
    clear() should remove all stored Order Blocks.
    """

    service = OrderBlockService()

    service.add(make_order_block())

    assert service.count() == 1

    service.clear()

    assert service.count() == 0

    assert service.get_all() == []