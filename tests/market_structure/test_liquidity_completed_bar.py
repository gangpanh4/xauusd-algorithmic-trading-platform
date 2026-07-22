from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.data.models import MarketBar
from core.market_structure.config import LiquidityDetectorConfig
from core.market_structure.enums import SwingType
from core.market_structure.liquidity_detector import LiquidityDetector
from core.market_structure.models import SwingPoint


def _swing(index: int, price: float, swing_type: SwingType) -> SwingPoint:
    return SwingPoint(
        timestamp=datetime(2025, 1, 1, tzinfo=UTC)
        + timedelta(minutes=15 * index),
        index=index,
        price=price,
        swing_type=swing_type,
        confirmation_index=index,
        pivot_dominance=0.5,
    )


def _bar(index: int, *, high: float, low: float, close: float) -> MarketBar:
    return MarketBar(
        timestamp=datetime(2025, 1, 1, tzinfo=UTC)
        + timedelta(minutes=15 * index),
        open=100.0,
        high=high,
        low=low,
        close=close,
        tick_volume=100,
    )


def test_buy_side_sweep_requires_reclaim_close() -> None:
    detector = LiquidityDetector()
    high = _swing(1, 100.0, SwingType.HIGH)
    detector.process_bar(
        _bar(1, high=100.0, low=99.0, close=99.5),
        bar_index=1,
        swing=high,
    )

    no_reclaim = detector.process_bar(
        _bar(2, high=101.0, low=99.0, close=100.5),
        bar_index=2,
        atr=1.0,
    )
    confirmation = _bar(3, high=101.0, low=98.0, close=99.0)
    event = detector.process_bar(
        confirmation,
        bar_index=3,
        atr=1.0,
    )

    assert no_reclaim is None
    assert event is not None
    assert event.timestamp == confirmation.timestamp
    assert event.liquidity_level is detector.state.liquidity_levels[0]
    assert event.sweep_price == 101.0
    assert event.sweep_distance == 1.0
    assert event.atr_multiple == 1.0
    assert event.reaction_strength == 1.0
    assert event.reclaim_strength == 1.0


def test_sell_side_sweep_requires_reclaim_close() -> None:
    detector = LiquidityDetector()
    low = _swing(1, 100.0, SwingType.LOW)
    detector.process_bar(
        _bar(1, high=101.0, low=100.0, close=100.5),
        bar_index=1,
        swing=low,
    )

    event = detector.process_bar(
        _bar(2, high=102.0, low=99.0, close=101.0),
        bar_index=2,
        atr=1.0,
    )

    assert event is not None
    assert event.timestamp == datetime(2025, 1, 1, 0, 30, tzinfo=UTC)
    assert event.sweep_price == 99.0
    assert event.reaction_strength == 1.0
    assert event.reclaim_strength == 1.0


def test_sweep_rejects_same_confirmation_bar() -> None:
    detector = LiquidityDetector()
    high = _swing(2, 100.0, SwingType.HIGH)

    event = detector.process_bar(
        _bar(2, high=101.0, low=98.0, close=99.0),
        bar_index=2,
        swing=high,
        atr=1.0,
    )

    assert event is None


def test_sweep_atr_threshold_fails_closed_without_atr() -> None:
    detector = LiquidityDetector(
        LiquidityDetectorConfig(minimum_sweep_atr_multiple=0.5)
    )
    high = _swing(1, 100.0, SwingType.HIGH)
    detector.process_bar(
        _bar(1, high=100.0, low=99.0, close=99.5),
        bar_index=1,
        swing=high,
    )
    bar = _bar(2, high=100.6, low=98.0, close=99.0)

    assert detector.process_bar(bar, bar_index=2) is None
    assert detector.process_bar(bar, bar_index=2, atr=1.0) is not None


def test_same_liquidity_level_can_only_be_swept_once() -> None:
    detector = LiquidityDetector()
    high = _swing(1, 100.0, SwingType.HIGH)
    detector.process_bar(
        _bar(1, high=100.0, low=99.0, close=99.5),
        bar_index=1,
        swing=high,
    )

    first = detector.process_bar(
        _bar(2, high=101.0, low=98.0, close=99.0),
        bar_index=2,
        atr=1.0,
    )
    second = detector.process_bar(
        _bar(3, high=102.0, low=98.0, close=99.0),
        bar_index=3,
        atr=1.0,
    )

    assert first is not None
    assert second is None
    assert detector.confirmed_sweep_count == 1


def test_reclaim_requirement_can_be_disabled_explicitly() -> None:
    detector = LiquidityDetector(
        LiquidityDetectorConfig(require_reclaim_close=False)
    )
    high = _swing(1, 100.0, SwingType.HIGH)
    detector.process_bar(
        _bar(1, high=100.0, low=99.0, close=99.5),
        bar_index=1,
        swing=high,
    )

    event = detector.process_bar(
        _bar(2, high=101.0, low=99.0, close=100.5),
        bar_index=2,
        atr=1.0,
    )

    assert event is not None
    assert event.reclaim_strength == 0.0
