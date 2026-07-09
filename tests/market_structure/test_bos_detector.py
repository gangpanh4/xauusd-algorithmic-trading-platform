"""
Unit tests for the Break of Structure (BOS) Detection Engine.
"""

from __future__ import annotations

from datetime import UTC, datetime

from core.market_structure.bos_detector import BOSDetector
from core.market_structure.config import BOSDetectorConfig
from core.market_structure.enums import (
    BreakType,
    DetectorStatus,
    SwingType,
)
from core.market_structure.models import (
    BOSEvent,
    SwingPoint,
)


def make_swing(
    *,
    index: int,
    price: float,
    swing_type: SwingType,
) -> SwingPoint:
    """
    Create a confirmed SwingPoint for testing.
    """

    return SwingPoint(
        timestamp=datetime.now(UTC),
        index=index,
        price=price,
        swing_type=swing_type,
        confirmation_index=index,
    )


def test_detector_initializes_with_default_config() -> None:
    """
    Detector should initialize using the default configuration.
    """

    detector = BOSDetector()

    assert isinstance(detector.config, BOSDetectorConfig)
    assert detector.state.processed_swing_count == 0
    assert detector.state.confirmed_swings == []
    assert detector.state.confirmed_breaks == []
    assert detector.state.last_break is None


def test_reset_clears_runtime_state() -> None:
    """
    Reset should restore the detector to its initial state.
    """

    detector = BOSDetector()

    swing = make_swing(
        index=1,
        price=100.0,
        swing_type=SwingType.HIGH,
    )

    detector.state.confirmed_swings.append(swing)
    detector.state.processed_swing_count = 5
    detector.state.detector_status = DetectorStatus.RUNNING

    detector.reset()

    assert detector.state.confirmed_swings == []
    assert detector.state.confirmed_breaks == []
    assert detector.state.last_break is None
    assert detector.state.processed_swing_count == 0
    assert detector.state.detector_status == DetectorStatus.WAITING


def test_process_returns_none_with_insufficient_swings() -> None:
    """
    One swing cannot produce a Break of Structure.
    """

    detector = BOSDetector()

    swing = make_swing(
        index=1,
        price=100.0,
        swing_type=SwingType.HIGH,
    )

    result = detector.process(swing)

    assert result is None


def test_add_swing_updates_runtime_state() -> None:
    """
    Adding a swing should update detector state.
    """

    detector = BOSDetector()

    swing = make_swing(
        index=1,
        price=100.0,
        swing_type=SwingType.HIGH,
    )

    detector._add_swing(swing)

    assert detector.state.processed_swing_count == 1
    assert detector.state.detector_status == DetectorStatus.RUNNING
    assert detector.state.confirmed_swings[-1] == swing


def test_duplicate_bos_is_rejected() -> None:
    """
    Duplicate BOS events should be rejected.
    """

    detector = BOSDetector()

    swing = make_swing(
        index=2,
        price=110.0,
        swing_type=SwingType.HIGH,
    )

    event = BOSEvent(
        timestamp=swing.timestamp,
        break_type=BreakType.BOS,
        swing_point=swing,
        confirmation_index=swing.confirmation_index,
    )

    detector.state.confirmed_breaks.append(event)

    assert detector._validate_break(event) is False


def test_get_last_break() -> None:
    """
    get_last_break should return the most recent break.
    """

    detector = BOSDetector()

    swing = make_swing(
        index=2,
        price=110.0,
        swing_type=SwingType.HIGH,
    )

    event = BOSEvent(
        timestamp=swing.timestamp,
        break_type=BreakType.BOS,
        swing_point=swing,
        confirmation_index=swing.confirmation_index,
    )

    detector.state.last_break = event

    assert detector.get_last_break() == event


def test_get_breaks() -> None:
    """
    get_breaks should return all confirmed breaks.
    """

    detector = BOSDetector()

    swing = make_swing(
        index=2,
        price=110.0,
        swing_type=SwingType.HIGH,
    )

    event = BOSEvent(
        timestamp=swing.timestamp,
        break_type=BreakType.BOS,
        swing_point=swing,
        confirmation_index=swing.confirmation_index,
    )

    detector.state.confirmed_breaks.append(event)

    assert detector.get_breaks() == [event]


def test_get_state() -> None:
    """
    get_state should return the detector runtime state.
    """

    detector = BOSDetector()

    assert detector.get_state() is detector.state


def test_get_previous_same_type_swing() -> None:
    """
    The previous swing of the same type should be returned.
    """

    detector = BOSDetector()

    high1 = make_swing(
        index=1,
        price=100.0,
        swing_type=SwingType.HIGH,
    )

    low = make_swing(
        index=2,
        price=90.0,
        swing_type=SwingType.LOW,
    )

    high2 = make_swing(
        index=3,
        price=110.0,
        swing_type=SwingType.HIGH,
    )

    detector.state.confirmed_swings.extend(
        [high1, low, high2]
    )

    assert detector._get_previous_same_type(high2) == high1

def test_get_previous_same_type_returns_none() -> None:
    """
    None should be returned when no previous swing of the same type exists.
    """

    detector = BOSDetector()

    high = make_swing(
        index=1,
        price=100.0,
        swing_type=SwingType.HIGH,
    )

    detector.state.confirmed_swings.append(high)

    assert detector._get_previous_same_type(high) is None

def test_detects_bullish_bos() -> None:
    """
    A higher confirmed swing high should produce a bullish BOS.
    """

    detector = BOSDetector()

    high1 = make_swing(
        index=1,
        price=100.0,
        swing_type=SwingType.HIGH,
    )

    low = make_swing(
        index=2,
        price=95.0,
        swing_type=SwingType.LOW,
    )

    high2 = make_swing(
        index=3,
        price=110.0,
        swing_type=SwingType.HIGH,
    )

    detector.process(high1)
    detector.process(low)

    event = detector.process(high2)

    assert event is not None
    assert event.break_type is BreakType.BOS
    assert event.swing_point == high2

def test_detects_bearish_bos() -> None:
    """
    A lower confirmed swing low should produce a bearish BOS.
    """

    detector = BOSDetector()

    low1 = make_swing(
        index=1,
        price=100.0,
        swing_type=SwingType.LOW,
    )

    high = make_swing(
        index=2,
        price=110.0,
        swing_type=SwingType.HIGH,
    )

    low2 = make_swing(
        index=3,
        price=90.0,
        swing_type=SwingType.LOW,
    )

    detector.process(low1)
    detector.process(high)

    event = detector.process(low2)

    assert event is not None
    assert event.break_type is BreakType.BOS
    assert event.swing_point == low2

def test_get_breaks_returns_copy() -> None:
    """
    get_breaks should return a copy rather than the internal list.
    """

    detector = BOSDetector()

    swing = make_swing(
        index=1,
        price=100.0,
        swing_type=SwingType.HIGH,
    )

    event = BOSEvent(
        timestamp=swing.timestamp,
        break_type=BreakType.BOS,
        swing_point=swing,
        confirmation_index=swing.confirmation_index,
    )

    detector.state.confirmed_breaks.append(event)

    breaks = detector.get_breaks()

    breaks.clear()

    assert len(detector.state.confirmed_breaks) == 1

