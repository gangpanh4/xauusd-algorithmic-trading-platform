from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.data.models import MarketBar
from core.market_structure.choch_detector import CHOCHDetector
from core.market_structure.config import CHOCHDetectorConfig
from core.market_structure.enums import MarketTrend, SwingType, TrendDirection
from core.market_structure.models import SwingPoint
from core.market_structure.state import BOSDetectorState


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


def test_bearish_choch_requires_close_below_protected_low() -> None:
    protected = _swing(1, 100.0, SwingType.LOW)
    bos_state = BOSDetectorState(
        current_trend=MarketTrend.BULLISH,
        protected_swing=protected,
    )
    detector = CHOCHDetector(bos_state)

    wick_only = detector.process_bar(
        _bar(2, high=101.0, low=99.0, close=100.2),
        bar_index=2,
    )
    confirmation = _bar(3, high=100.0, low=98.0, close=99.0)
    event = detector.process_bar(confirmation, bar_index=3)

    assert wick_only is None
    assert event is not None
    assert event.direction is TrendDirection.BEARISH
    assert event.swing_point is protected
    assert event.timestamp == confirmation.timestamp
    assert event.break_price == confirmation.close


def test_bullish_choch_changes_trend_and_protected_swing() -> None:
    protected = _swing(1, 105.0, SwingType.HIGH)
    new_low = _swing(2, 95.0, SwingType.LOW)
    bos_state = BOSDetectorState(
        confirmed_swings=[protected, new_low],
        current_trend=MarketTrend.BEARISH,
        protected_swing=protected,
    )
    detector = CHOCHDetector(bos_state)
    detector.process_bar(
        _bar(2, high=100.0, low=95.0, close=98.0),
        bar_index=2,
        swing=new_low,
    )

    event = detector.process_bar(
        _bar(3, high=107.0, low=100.0, close=106.0),
        bar_index=3,
    )

    assert event is not None
    assert event.direction is TrendDirection.BULLISH
    assert bos_state.current_trend is MarketTrend.BULLISH
    assert bos_state.protected_swing is new_low


def test_choch_respects_minimum_break_distance() -> None:
    protected = _swing(1, 100.0, SwingType.LOW)
    bos_state = BOSDetectorState(
        current_trend=MarketTrend.BULLISH,
        protected_swing=protected,
    )
    detector = CHOCHDetector(
        bos_state,
        CHOCHDetectorConfig(minimum_break_distance=1.0),
    )

    assert detector.process_bar(
        _bar(2, high=101.0, low=99.2, close=99.2),
        bar_index=2,
    ) is None

    assert detector.process_bar(
        _bar(3, high=100.0, low=98.5, close=98.5),
        bar_index=3,
    ) is not None


def test_choch_does_not_repeat_same_protected_swing() -> None:
    protected = _swing(1, 100.0, SwingType.LOW)
    bos_state = BOSDetectorState(
        current_trend=MarketTrend.BULLISH,
        protected_swing=protected,
    )
    detector = CHOCHDetector(bos_state)

    first = detector.process_bar(
        _bar(2, high=101.0, low=98.0, close=99.0),
        bar_index=2,
    )
    # Restore the original trend to prove duplicate protection is event-based.
    bos_state.current_trend = MarketTrend.BULLISH
    bos_state.protected_swing = protected
    second = detector.process_bar(
        _bar(3, high=100.0, low=97.0, close=98.0),
        bar_index=3,
    )

    assert first is not None
    assert second is None
    assert detector.confirmed_change_count == 1


def test_choch_atr_threshold_fails_closed_without_atr() -> None:
    protected = _swing(1, 100.0, SwingType.LOW)
    bos_state = BOSDetectorState(
        current_trend=MarketTrend.BULLISH,
        protected_swing=protected,
    )
    detector = CHOCHDetector(
        bos_state,
        CHOCHDetectorConfig(minimum_break_atr_multiple=0.5),
    )

    bar = _bar(2, high=101.0, low=99.0, close=99.0)
    assert detector.process_bar(bar, bar_index=2) is None
    event = detector.process_bar(bar, bar_index=2, atr=1.0)
    assert event is not None
    assert event.break_atr_multiple == pytest.approx(1.0)
