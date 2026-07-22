from __future__ import annotations

from datetime import UTC, datetime
from math import exp

import pytest

from core.market_structure.enums import BreakType, SwingType, TrendDirection
from core.market_structure.models import (
    BOSEvent,
    LiquidityLevel,
    LiquiditySweepEvent,
    SwingPoint,
)
from core.market_structure.swing_evaluator import StructureEvaluator


def _swing() -> SwingPoint:
    return SwingPoint(
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        index=0,
        price=100.0,
        swing_type=SwingType.HIGH,
        confirmation_index=0,
        confirmation_strength=1.0,
    )


def test_event_quality_is_decayed_by_completed_bar_age() -> None:
    swing = _swing()
    bos = BOSEvent(
        timestamp=swing.timestamp,
        break_type=BreakType.BOS,
        direction=TrendDirection.BULLISH,
        swing_point=swing,
        break_price=101.0,
        confirmation_index=0,
        break_distance=100.0,
        quality=0.8,
        age=8,
    )
    evaluator = StructureEvaluator(freshness_decay_bars=8)

    result = evaluator.evaluate(
        swing=None,
        bos=bos,
        choch=None,
        liquidity=None,
    )

    assert result.bos_freshness == pytest.approx(exp(-1.0))
    assert result.bos_score == pytest.approx(0.8 * exp(-1.0))


def test_larger_raw_break_distance_does_not_inflate_score() -> None:
    swing = _swing()
    small = BOSEvent(
        timestamp=swing.timestamp,
        break_type=BreakType.BOS,
        direction=TrendDirection.BULLISH,
        swing_point=swing,
        break_price=101.0,
        confirmation_index=0,
        break_distance=1.0,
        quality=0.6,
    )
    large = BOSEvent(
        timestamp=swing.timestamp,
        break_type=BreakType.BOS,
        direction=TrendDirection.BULLISH,
        swing_point=swing,
        break_price=200.0,
        confirmation_index=0,
        break_distance=100.0,
        quality=0.6,
    )
    evaluator = StructureEvaluator()

    small_score = evaluator.evaluate(
        swing=None,
        bos=small,
        choch=None,
        liquidity=None,
    ).bos_score
    large_score = evaluator.evaluate(
        swing=None,
        bos=large,
        choch=None,
        liquidity=None,
    ).bos_score

    assert small_score == large_score == 0.6


def test_liquidity_quality_and_freshness_drive_liquidity_score() -> None:
    swing = _swing()
    level = LiquidityLevel(
        timestamp=swing.timestamp,
        price=swing.price,
        swing_point=swing,
        is_buy_side=True,
    )
    event = LiquiditySweepEvent(
        timestamp=swing.timestamp,
        liquidity_level=level,
        sweep_price=101.0,
        confirmation_index=0,
        quality=0.5,
        age=4,
    )
    evaluator = StructureEvaluator(freshness_decay_bars=4)

    result = evaluator.evaluate(
        swing=None,
        bos=None,
        choch=None,
        liquidity=event,
    )

    assert result.liquidity_freshness == pytest.approx(exp(-1.0))
    assert result.liquidity_score == pytest.approx(0.5 * exp(-1.0))


def test_weights_are_normalized() -> None:
    evaluator = StructureEvaluator(
        swing_weight=2.0,
        bos_weight=3.5,
        choch_weight=2.0,
        liquidity_weight=2.5,
    )

    assert (
        evaluator.swing_weight
        + evaluator.bos_weight
        + evaluator.choch_weight
        + evaluator.liquidity_weight
    ) == pytest.approx(1.0)
