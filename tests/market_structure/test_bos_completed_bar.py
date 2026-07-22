from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.data.models import MarketBar
from core.market_structure.bos_detector import BOSDetector
from core.market_structure.config import BOSDetectorConfig
from core.market_structure.enums import SwingType, TrendDirection
from core.market_structure.models import SwingPoint


def _swing(
    *,
    index: int,
    price: float,
    swing_type: SwingType,
) -> SwingPoint:
    return SwingPoint(
        timestamp=datetime(2025, 1, 1, tzinfo=UTC)
        + timedelta(minutes=15 * index),
        index=index,
        price=price,
        swing_type=swing_type,
        confirmation_index=index,
        pivot_dominance=0.5,
    )


def _bar(
    *,
    index: int,
    high: float,
    low: float,
    close: float,
) -> MarketBar:
    return MarketBar(
        timestamp=datetime(2025, 1, 1, tzinfo=UTC)
        + timedelta(minutes=15 * index),
        open=100.0,
        high=high,
        low=low,
        close=close,
        tick_volume=100,
    )


def test_completed_bar_bos_requires_close_by_default() -> None:
    detector = BOSDetector()
    high = _swing(index=1, price=100.0, swing_type=SwingType.HIGH)
    detector.process_bar(_bar(index=1, high=100.0, low=99.0, close=99.5), bar_index=1, swing=high)

    event = detector.process_bar(
        _bar(index=2, high=101.0, low=99.0, close=99.8),
        bar_index=2,
    )

    assert event is None


def test_completed_bar_bos_uses_confirmation_candle_timestamp() -> None:
    detector = BOSDetector()
    high = _swing(index=1, price=100.0, swing_type=SwingType.HIGH)
    low = _swing(index=2, price=95.0, swing_type=SwingType.LOW)
    detector.process_bar(_bar(index=1, high=100.0, low=99.0, close=99.5), bar_index=1, swing=high)
    detector.process_bar(_bar(index=2, high=99.0, low=95.0, close=97.0), bar_index=2, swing=low)
    confirmation_bar = _bar(index=3, high=102.0, low=99.0, close=101.5)

    event = detector.process_bar(confirmation_bar, bar_index=3)

    assert event is not None
    assert event.direction is TrendDirection.BULLISH
    assert event.swing_point is high
    assert event.timestamp == confirmation_bar.timestamp
    assert event.confirmation_index == 3
    assert event.break_price == confirmation_bar.close
    assert event.break_distance == 1.5
    assert event.break_atr_multiple == 0.0
    assert detector.state.protected_swing is low


def test_completed_bar_bos_can_allow_wick_break_explicitly() -> None:
    detector = BOSDetector(
        BOSDetectorConfig(
            require_close_break=False,
            allow_wick_break=True,
        )
    )
    high = _swing(index=1, price=100.0, swing_type=SwingType.HIGH)
    detector.process_bar(_bar(index=1, high=100.0, low=99.0, close=99.0), bar_index=1, swing=high)

    event = detector.process_bar(
        _bar(index=2, high=101.0, low=98.0, close=99.5),
        bar_index=2,
    )

    assert event is not None
    assert event.break_price == 101.0


def test_completed_bar_bos_respects_atr_threshold() -> None:
    detector = BOSDetector(
        BOSDetectorConfig(minimum_break_atr_multiple=0.5)
    )
    high = _swing(index=1, price=100.0, swing_type=SwingType.HIGH)
    detector.process_bar(_bar(index=1, high=100.0, low=99.0, close=99.0), bar_index=1, swing=high)

    assert detector.process_bar(
        _bar(index=2, high=100.4, low=99.0, close=100.4),
        bar_index=2,
        atr=1.0,
    ) is None

    event = detector.process_bar(
        _bar(index=3, high=100.6, low=99.0, close=100.6),
        bar_index=3,
        atr=1.0,
    )
    assert event is not None
    assert event.break_atr_multiple == pytest.approx(0.6)


def test_completed_bar_does_not_repeat_same_broken_level() -> None:
    detector = BOSDetector()
    high = _swing(index=1, price=100.0, swing_type=SwingType.HIGH)
    detector.process_bar(_bar(index=1, high=100.0, low=99.0, close=99.0), bar_index=1, swing=high)

    first = detector.process_bar(
        _bar(index=2, high=101.0, low=99.0, close=101.0),
        bar_index=2,
    )
    second = detector.process_bar(
        _bar(index=3, high=102.0, low=100.0, close=102.0),
        bar_index=3,
    )

    assert first is not None
    assert second is None
    assert detector.confirmed_break_count == 1
