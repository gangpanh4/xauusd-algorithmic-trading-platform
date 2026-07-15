"""
Unit tests for the Change of Character (CHOCH) Detection Engine.
"""

from __future__ import annotations

from datetime import UTC, datetime

from core.market_structure.choch_detector import CHOCHDetector
from core.market_structure.config import CHOCHDetectorConfig
from core.market_structure.enums import (
    DetectorStatus,
    MarketTrend,
    SwingType,
    TrendDirection,
)
from core.market_structure.state import BOSDetectorState
from core.market_structure.models import SwingPoint


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
    Detector should initialize correctly.
    """

    bos_state = BOSDetectorState()

    detector = CHOCHDetector(
        bos_state=bos_state,
    )

    assert isinstance(
        detector.config,
        CHOCHDetectorConfig,
    )
    assert detector.state.confirmed_changes == []
    assert detector.state.last_change is None

def test_reset_clears_runtime_state() -> None:
    """
    Reset should restore the CHOCH detector state.
    """

    bos_state = BOSDetectorState()

    detector = CHOCHDetector(
        bos_state=bos_state,
    )

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
    assert detector.state.confirmed_changes == []
    assert detector.state.last_change is None
    assert detector.state.processed_swing_count == 0
    assert detector.state.detector_status == DetectorStatus.WAITING

def test_process_updates_runtime_state() -> None:
    """
    Processing a swing should update CHOCH runtime state.
    """

    bos_state = BOSDetectorState()

    detector = CHOCHDetector(
        bos_state=bos_state,
    )

    swing = make_swing(
        index=1,
        price=100.0,
        swing_type=SwingType.HIGH,
    )

    result = detector.process(swing)

    assert result is None
    assert detector.state.processed_swing_count == 1
    assert detector.state.confirmed_swings[-1] == swing

def test_detects_bearish_choch() -> None:
    """
    Bullish structure breaking below the protected swing
    should create a bearish CHOCH.
    """

    bos_state = BOSDetectorState()

    bos_state.current_trend = MarketTrend.BULLISH

    bos_state.protected_swing = make_swing(
        index=1,
        price=100.0,
        swing_type=SwingType.LOW,
    )

    detector = CHOCHDetector(
        bos_state=bos_state,
    )

    breaking_swing = make_swing(
        index=2,
        price=95.0,
        swing_type=SwingType.LOW,
    )

    result = detector.process(
        breaking_swing
    )

    assert result is not None
    assert result.swing_point == breaking_swing
    assert detector.state.last_change == result

def test_detects_bullish_choch() -> None:
    """
    Bearish structure breaking above the protected swing
    should create a bullish CHOCH.
    """

    bos_state = BOSDetectorState()

    bos_state.current_trend = MarketTrend.BEARISH

    bos_state.protected_swing = make_swing(
        index=1,
        price=200.0,
        swing_type=SwingType.HIGH,
    )

    detector = CHOCHDetector(
        bos_state=bos_state,
    )

    breaking_swing = make_swing(
        index=2,
        price=205.0,
        swing_type=SwingType.HIGH,
    )

    result = detector.process(
        breaking_swing
    )

    assert result is not None
    assert result.swing_point == breaking_swing
    assert detector.state.last_change == result

def test_no_choch_without_protected_swing() -> None:
    """
    CHOCH should not occur without a protected swing.
    """

    bos_state = BOSDetectorState()

    bos_state.current_trend = MarketTrend.BULLISH
    bos_state.protected_swing = None

    detector = CHOCHDetector(
        bos_state=bos_state,
    )

    swing = make_swing(
        index=1,
        price=95.0,
        swing_type=SwingType.LOW,
    )

    result = detector.process(swing)

    assert result is None

def test_wrong_trend_does_not_create_choch() -> None:
    """
    A swing opposite to the expected trend should not
    produce a CHOCH.
    """

    bos_state = BOSDetectorState()

    bos_state.current_trend = MarketTrend.BEARISH

    bos_state.protected_swing = make_swing(
        index=1,
        price=200.0,
        swing_type=SwingType.HIGH,
    )

    detector = CHOCHDetector(
        bos_state=bos_state,
    )

    swing = make_swing(
        index=2,
        price=95.0,
        swing_type=SwingType.LOW,
    )

    result = detector.process(swing)

    assert result is None

def test_wrong_swing_type_does_not_create_choch() -> None:
    """
    A swing of the wrong type should not create CHOCH.
    """

    bos_state = BOSDetectorState()

    bos_state.current_trend = MarketTrend.BULLISH

    bos_state.protected_swing = make_swing(
        index=1,
        price=100.0,
        swing_type=SwingType.LOW,
    )

    detector = CHOCHDetector(
        bos_state=bos_state,
    )

    swing = make_swing(
        index=2,
        price=120.0,
        swing_type=SwingType.HIGH,
    )

    result = detector.process(swing)

    assert result is None

def test_duplicate_choch_is_rejected() -> None:
    """
    Duplicate CHOCH events should not be created.
    """

    bos_state = BOSDetectorState()

    bos_state.current_trend = MarketTrend.BULLISH

    bos_state.protected_swing = make_swing(
        index=1,
        price=100.0,
        swing_type=SwingType.LOW,
    )

    detector = CHOCHDetector(
        bos_state=bos_state,
    )

    swing = make_swing(
        index=2,
        price=95.0,
        swing_type=SwingType.LOW,
    )

    first = detector.process(swing)
    second = detector.process(swing)

    assert first is not None
    assert second is None