from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.data.models import MarketBar
from core.market_structure.config import SwingDetectorConfig
from core.market_structure.enums import SwingClassification, SwingType
from core.market_structure.models import SwingPoint
from core.market_structure.swing_detector import SwingDetector


def _swing(price: float, swing_type: SwingType, index: int) -> SwingPoint:
    return SwingPoint(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index),
        index=index,
        price=price,
        swing_type=swing_type,
        confirmation_index=index + 1,
    )


def _bar(index: int, high: float, low: float) -> MarketBar:
    return MarketBar(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index),
        open=(high + low) / 2.0,
        high=high,
        low=low,
        close=(high + low) / 2.0,
        tick_volume=100,
    )


def test_classifies_hh_hl_lh_ll_and_equal_levels() -> None:
    detector = SwingDetector(
        SwingDetectorConfig(
            atr_validation=False,
            equal_high_tolerance=0.2,
            equal_low_tolerance=0.2,
        )
    )
    detector.state.confirmed_swings[:] = [
        _swing(100.0, SwingType.HIGH, 1),
        _swing(90.0, SwingType.LOW, 2),
    ]
    detector.state.last_swing = detector.state.confirmed_swings[-1]

    assert detector._classify_swing(_swing(105.0, SwingType.HIGH, 3)).classification is SwingClassification.HIGHER_HIGH
    assert detector._classify_swing(_swing(95.0, SwingType.HIGH, 3)).classification is SwingClassification.LOWER_HIGH
    assert detector._classify_swing(_swing(100.1, SwingType.HIGH, 3)).classification is SwingClassification.EQUAL_HIGH

    detector.state.confirmed_swings[:] = [
        _swing(90.0, SwingType.LOW, 1),
        _swing(100.0, SwingType.HIGH, 2),
    ]
    detector.state.last_swing = detector.state.confirmed_swings[-1]

    assert detector._classify_swing(_swing(95.0, SwingType.LOW, 3)).classification is SwingClassification.HIGHER_LOW
    assert detector._classify_swing(_swing(85.0, SwingType.LOW, 3)).classification is SwingClassification.LOWER_LOW
    assert detector._classify_swing(_swing(89.9, SwingType.LOW, 3)).classification is SwingClassification.EQUAL_LOW


def test_more_extreme_consecutive_high_replaces_stale_candidate() -> None:
    detector = SwingDetector(
        SwingDetectorConfig(
            pivot_left=1,
            pivot_right=1,
            atr_validation=False,
            minimum_swing_distance=0.0,
        )
    )
    bars = [
        _bar(0, 100.0, 90.0),
        _bar(1, 110.0, 95.0),
        _bar(2, 105.0, 96.0),
        _bar(3, 115.0, 97.0),
        _bar(4, 120.0, 98.0),
        _bar(5, 110.0, 99.0),
    ]

    emitted = [result for bar in bars if (result := detector.process(bar)) is not None]

    assert [item.price for item in emitted] == [110.0, 120.0]
    assert len(detector.get_swings()) == 1
    assert detector.get_last_swing() is not None
    assert detector.get_last_swing().price == 120.0
    assert detector.get_last_swing().confirmation_index == 5


def test_less_extreme_consecutive_high_does_not_replace_candidate() -> None:
    detector = SwingDetector(SwingDetectorConfig(atr_validation=False))
    original = _swing(110.0, SwingType.HIGH, 1)
    detector.state.confirmed_swings.append(original)
    detector.state.last_swing = original

    assert detector._replace_same_type_swing(_swing(108.0, SwingType.HIGH, 2)) is None
    assert detector.get_last_swing() == original
