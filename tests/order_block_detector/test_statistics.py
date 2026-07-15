"""
Unit tests for Order Block statistics.
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
from core.order_block_detector.statistics import (
    OrderBlockStatistics,
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


def make_order_block(
    block_type: OrderBlockType,
) -> OrderBlock:
    """
    Create an Order Block.
    """

    swing = make_swing()

    return OrderBlock(
        timestamp=datetime.now(timezone.utc),
        block_type=block_type,
        top_price=101.0,
        bottom_price=100.0,
        origin_swing=swing,
        trigger_break=make_break(),
        trigger_liquidity=None,
        creation_index=2,
        confirmation_index=3,
    )


def test_total_blocks() -> None:
    """
    total_blocks() should return the correct count.
    """

    statistics = OrderBlockStatistics()

    blocks = [
        make_order_block(OrderBlockType.BULLISH),
        make_order_block(OrderBlockType.BEARISH),
    ]

    assert statistics.total_blocks(blocks) == 2


def test_bullish_blocks() -> None:
    """
    bullish_blocks() should count bullish Order Blocks.
    """

    statistics = OrderBlockStatistics()

    blocks = [
        make_order_block(OrderBlockType.BULLISH),
        make_order_block(OrderBlockType.BULLISH),
        make_order_block(OrderBlockType.BEARISH),
    ]

    assert statistics.bullish_blocks(blocks) == 2


def test_bearish_blocks() -> None:
    """
    bearish_blocks() should count bearish Order Blocks.
    """

    statistics = OrderBlockStatistics()

    blocks = [
        make_order_block(OrderBlockType.BULLISH),
        make_order_block(OrderBlockType.BEARISH),
        make_order_block(OrderBlockType.BEARISH),
    ]

    assert statistics.bearish_blocks(blocks) == 2