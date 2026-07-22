from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.data.models import MarketBar
from core.market_structure.enums import BreakType, OrderBlockType, SwingType, TrendDirection
from core.market_structure.models import BOSEvent, LiquidityLevel, LiquiditySweepEvent, SwingPoint
from core.order_block_detector.config import OrderBlockDetectorConfig
from core.order_block_detector.detector import OrderBlockDetector


def bar(index: int, *, open_: float, high: float, low: float, close: float) -> MarketBar:
    return MarketBar(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=15 * index),
        open=open_, high=high, low=low, close=close, tick_volume=100,
    )


def bullish_break() -> BOSEvent:
    swing = SwingPoint(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        index=0,
        price=2000.0,
        swing_type=SwingType.HIGH,
        confirmation_index=2,
    )
    return BOSEvent(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=45),
        break_type=BreakType.BOS,
        direction=TrendDirection.BULLISH,
        swing_point=swing,
        break_price=2002.0,
        confirmation_index=3,
        break_distance=2.0,
        break_atr_multiple=1.8,
        quality=0.9,
        strength=0.8,
        structure_score=0.85,
    )


def liquidity() -> LiquiditySweepEvent:
    swing = SwingPoint(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        index=0,
        price=1998.0,
        swing_type=SwingType.LOW,
        confirmation_index=1,
    )
    return LiquiditySweepEvent(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=30),
        liquidity_level=LiquidityLevel(
            timestamp=swing.timestamp,
            price=swing.price,
            swing_point=swing,
            is_buy_side=False,
        ),
        sweep_price=1997.5,
        confirmation_index=2,
        quality=0.9,
        sweep_strength=0.8,
        reaction_strength=0.9,
        reclaim_strength=0.8,
    )


def bars() -> list[MarketBar]:
    return [
        bar(0, open_=2000.0, high=2000.5, low=1999.5, close=2000.2),
        bar(1, open_=2000.2, high=2000.3, low=1999.0, close=1999.2),
        bar(2, open_=1999.2, high=2001.0, low=1999.1, close=2000.8),
        bar(3, open_=2000.8, high=2002.2, low=2000.5, close=2002.0),
    ]


def test_real_bullish_break_creates_origin_block() -> None:
    detector = OrderBlockDetector(OrderBlockDetectorConfig(minimum_strength=0.5))
    event = detector.process(break_event=bullish_break(), bars=bars(), liquidity_event=liquidity())
    assert event is not None
    assert event.order_block.block_type is OrderBlockType.BULLISH
    assert event.order_block.timestamp == bars()[1].timestamp
    assert event.order_block.top_price == 2000.3
    assert event.order_block.bottom_price == 1999.0
    assert event.analysis.total_score >= 0.5
    assert event.analysis.displacement_score == pytest.approx(0.9)
    assert event.analysis.liquidity_score > 0.0


def test_same_break_is_not_confirmed_twice() -> None:
    detector = OrderBlockDetector(OrderBlockDetectorConfig(minimum_strength=0.5))
    first = detector.process(break_event=bullish_break(), bars=bars())
    second = detector.process(break_event=bullish_break(), bars=bars())
    assert first is not None
    assert second is None
    assert len(detector.get_order_blocks()) == 1


def test_nearest_opposite_candle_is_selected() -> None:
    window = bars()
    window.insert(2, bar(2, open_=2000.0, high=2000.2, low=1998.8, close=1999.0))
    # Restore strict chronology after insertion.
    window = [
        bar(0, open_=2000.0, high=2000.5, low=1999.5, close=2000.2),
        bar(1, open_=2000.2, high=2000.3, low=1999.0, close=1999.2),
        bar(2, open_=2000.0, high=2000.2, low=1998.8, close=1999.0),
        bar(3, open_=1999.0, high=2002.2, low=1998.9, close=2002.0),
    ]
    detector = OrderBlockDetector(OrderBlockDetectorConfig(minimum_strength=0.4))
    event = detector.process(break_event=bullish_break(), bars=window)
    assert event is not None
    assert event.order_block.timestamp == window[2].timestamp


def test_invalid_bar_order_fails_closed() -> None:
    detector = OrderBlockDetector()
    with pytest.raises(ValueError, match="strictly increasing"):
        detector.process(break_event=bullish_break(), bars=list(reversed(bars())))


def test_high_minimum_strength_rejects_weak_candidate() -> None:
    weak = bullish_break()
    weak = BOSEvent(
        timestamp=weak.timestamp,
        break_type=weak.break_type,
        direction=weak.direction,
        swing_point=weak.swing_point,
        break_price=2000.11,
        confirmation_index=weak.confirmation_index,
        break_distance=0.11,
        break_atr_multiple=0.05,
        quality=0.1,
        strength=0.1,
        structure_score=0.1,
    )
    detector = OrderBlockDetector(OrderBlockDetectorConfig(minimum_strength=0.9))
    assert detector.process(break_event=weak, bars=bars()) is None
    assert detector.get_order_blocks() == []
    assert detector.state.pending_candidates == []


def test_nested_overlap_is_rejected_by_default() -> None:
    detector = OrderBlockDetector(OrderBlockDetectorConfig(minimum_strength=0.4))
    assert detector.process(break_event=bullish_break(), bars=bars()) is not None
    other = bullish_break()
    other = BOSEvent(
        timestamp=other.timestamp + timedelta(minutes=15),
        break_type=other.break_type,
        direction=other.direction,
        swing_point=other.swing_point,
        break_price=2002.2,
        confirmation_index=4,
        break_distance=2.2,
        break_atr_multiple=2.0,
        quality=0.9,
        strength=0.9,
        structure_score=0.9,
    )
    assert detector.process(break_event=other, bars=bars()) is None
    assert len(detector.get_order_blocks()) == 1


def test_invalid_configuration_fails_closed() -> None:
    with pytest.raises(ValueError, match="minimum_strength"):
        OrderBlockDetector(OrderBlockDetectorConfig(minimum_strength=1.1))
