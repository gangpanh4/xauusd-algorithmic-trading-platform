"""
Unit tests for the Order Block Validator.
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
    OrderBlockCandidate,
)
from core.order_block_detector.validator import (
    OrderBlockValidator,
)


def make_swing() -> SwingPoint:
    """
    Create a confirmed swing point for testing.
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
    Create a valid BOS event for testing.
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


def make_candidate() -> OrderBlockCandidate:
    """
    Create a valid Order Block candidate.
    """

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


def test_valid_candidate_is_accepted() -> None:
    """
    A structurally valid candidate should pass validation.
    """

    validator = OrderBlockValidator()

    assert validator.validate(
        make_candidate()
    )


def test_invalid_price_range_is_rejected() -> None:
    """
    Top price below bottom price should fail validation.
    """

    validator = OrderBlockValidator()

    candidate = make_candidate()

    invalid_candidate = OrderBlockCandidate(
        timestamp=candidate.timestamp,
        block_type=candidate.block_type,
        top_price=99.0,
        bottom_price=100.0,
        origin_swing=candidate.origin_swing,
        trigger_break=candidate.trigger_break,
        trigger_liquidity=candidate.trigger_liquidity,
        creation_index=candidate.creation_index,
    )

    assert not validator.validate(
        invalid_candidate
    )