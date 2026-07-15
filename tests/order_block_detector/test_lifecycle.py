"""
Unit tests for the Order Block lifecycle manager.
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
from core.order_block_detector.lifecycle import (
    OrderBlockLifecycle,
)
from core.order_block_detector.models import (
    OrderBlock,
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


def test_order_block_is_active() -> None:
    lifecycle = OrderBlockLifecycle()

    assert lifecycle.is_active(
        make_order_block()
    )


def test_order_block_is_not_mitigated() -> None:
    lifecycle = OrderBlockLifecycle()

    assert not lifecycle.is_mitigated(
        make_order_block()
    )


def test_order_block_is_not_invalidated() -> None:
    lifecycle = OrderBlockLifecycle()

    assert not lifecycle.is_invalidated(
        make_order_block()
    )


def test_order_block_is_not_expired() -> None:
    lifecycle = OrderBlockLifecycle()

    assert not lifecycle.is_expired(
        make_order_block()
    )