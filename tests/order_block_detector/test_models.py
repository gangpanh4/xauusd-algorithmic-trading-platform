"""
Unit tests for Order Block domain models.
"""

from __future__ import annotations

from datetime import datetime, timezone

from core.market_structure.enums import (
    BreakType,
    MarketTrend,
    OrderBlockEventType,
    OrderBlockType,
    SwingType,
)
from core.market_structure.models import (
    BOSEvent,
    SwingPoint,
)
from core.order_block_detector.models import (
    OrderBlock,
    OrderBlockAnalysis,
    OrderBlockCandidate,
    OrderBlockEvent,
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


def make_candidate() -> OrderBlockCandidate:
    swing = make_swing()

    return OrderBlockCandidate(
        timestamp=datetime.now(timezone.utc),
        block_type=OrderBlockType.BULLISH,
        top_price=101.0,
        bottom_price=100.0,
        origin_swing=swing,
        trigger_break=make_break(),
        trigger_liquidity=None,
        creation_index=2,
    )


def make_order_block() -> OrderBlock:
    candidate = make_candidate()

    return OrderBlock(
        timestamp=candidate.timestamp,
        block_type=candidate.block_type,
        top_price=candidate.top_price,
        bottom_price=candidate.bottom_price,
        origin_swing=candidate.origin_swing,
        trigger_break=candidate.trigger_break,
        trigger_liquidity=candidate.trigger_liquidity,
        creation_index=candidate.creation_index,
        confirmation_index=3,
    )


def test_order_block_candidate_creation() -> None:
    candidate = make_candidate()

    assert candidate.block_type is OrderBlockType.BULLISH
    assert candidate.top_price == 101.0
    assert candidate.bottom_price == 100.0


def test_order_block_creation() -> None:
    block = make_order_block()

    assert block.confirmation_index == 3
    assert block.block_type is OrderBlockType.BULLISH


def test_order_block_analysis_creation() -> None:
    analysis = OrderBlockAnalysis(
        structure_score=0.90,
        displacement_score=0.85,
        liquidity_score=0.80,
        reaction_score=0.75,
        total_score=0.83,
    )

    assert analysis.total_score == 0.83


def test_order_block_event_creation() -> None:
    block = make_order_block()

    analysis = OrderBlockAnalysis(
        structure_score=1.0,
        displacement_score=1.0,
        liquidity_score=1.0,
        reaction_score=1.0,
        total_score=1.0,
    )

    event = OrderBlockEvent(
        timestamp=datetime.now(timezone.utc),
        event_type=OrderBlockEventType.CREATED,
        order_block=block,
        analysis=analysis,
        confirmation_index=3,
    )

    assert event.event_type is OrderBlockEventType.CREATED
    assert event.order_block is block