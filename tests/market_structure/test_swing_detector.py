"""
Unit tests for the Swing Detection Engine.
"""

from __future__ import annotations

from datetime import UTC, datetime

from core.data.market_data import MarketBar
from core.market_structure.config import SwingDetectorConfig
from core.market_structure.enums import SwingType
from core.market_structure.state import SwingDetectorState
from core.market_structure.swing_detector import SwingDetector


def test_detector_initializes_with_default_config() -> None:
    """
    The detector should initialize with a default configuration
    and an empty runtime state.
    """

    detector = SwingDetector()

    assert isinstance(
        detector.config,
        SwingDetectorConfig,
    )

    assert isinstance(
        detector.state,
        SwingDetectorState,
    )


def test_reset_clears_runtime_state() -> None:
    """
    Reset should restore the detector to its initial state.
    """

    detector = SwingDetector()

    detector.state.processed_bar_count = 10
    detector.state.detector_status = "RUNNING"

    detector.reset()

    assert detector.state.processed_bar_count == 0
    assert detector.state.detector_status == "WAITING"
    assert len(detector.state.recent_bars) == 0
    assert len(detector.state.confirmed_swings) == 0
    assert detector.state.last_swing is None


def test_process_returns_none_with_insufficient_history() -> None:
    """
    The detector should not emit a swing until enough
    history has been collected.
    """

    detector = SwingDetector()

    bar = MarketBar(
        timestamp=datetime.now(UTC),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        tick_volume=100,
    )

    result = detector.process(bar)

    assert result is None


def test_history_buffer_respects_maximum_history() -> None:
    """
    Processing bars should never allow the rolling history
    to exceed the configured maximum.
    """

    config = SwingDetectorConfig(
        maximum_history=5,
        pivot_left=1,
        pivot_right=1,
        atr_period=1,
    )

    detector = SwingDetector(config)

    for i in range(10):
        detector.process(
            MarketBar(
                timestamp=datetime.now(UTC),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                tick_volume=i,
            )
        )

    assert len(detector.state.recent_bars) == 5


def test_no_swing_detected_in_flat_market() -> None:
    """
    A flat market should not produce any confirmed swings.
    """

    config = SwingDetectorConfig(
        pivot_left=1,
        pivot_right=1,
        atr_validation=False,
    )

    detector = SwingDetector(config)

    bars = [
        MarketBar(
            timestamp=datetime.now(UTC),
            open=100.0,
            high=100.0,
            low=100.0,
            close=100.0,
            tick_volume=100,
        )
        for _ in range(5)
    ]

    results = [
        detector.process(bar)
        for bar in bars
    ]

    assert all(result is None for result in results)


def test_detects_confirmed_swing_high() -> None:
    """
    A valid pivot high should produce one confirmed Swing High.
    """

    config = SwingDetectorConfig(
        pivot_left=1,
        pivot_right=1,
        atr_validation=False,
        minimum_swing_distance=0.0,
    )

    detector = SwingDetector(config)

    bars = [
        MarketBar(
            timestamp=datetime.now(UTC),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            tick_volume=100,
        ),
        MarketBar(
            timestamp=datetime.now(UTC),
            open=101.0,
            high=105.0,
            low=100.0,
            close=104.0,
            tick_volume=100,
        ),
        MarketBar(
            timestamp=datetime.now(UTC),
            open=100.0,
            high=102.0,
            low=99.0,
            close=100.0,
            tick_volume=100,
        ),
    ]

    result = None

    for bar in bars:
        detected = detector.process(bar)

        if detected is not None:
            result = detected

    assert result is not None
    assert result.swing_type is SwingType.HIGH
    assert result.price == 105.0
    assert detector.get_last_swing() == result


def test_detects_confirmed_swing_low() -> None:
    """
    A valid pivot low should produce one confirmed Swing Low.
    """

    config = SwingDetectorConfig(
        pivot_left=1,
        pivot_right=1,
        atr_validation=False,
        minimum_swing_distance=0.0,
    )

    detector = SwingDetector(config)

    bars = [
        MarketBar(
            timestamp=datetime.now(UTC),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            tick_volume=100,
        ),
        MarketBar(
            timestamp=datetime.now(UTC),
            open=99.0,
            high=100.0,
            low=95.0,
            close=96.0,
            tick_volume=100,
        ),
        MarketBar(
            timestamp=datetime.now(UTC),
            open=100.0,
            high=101.0,
            low=98.0,
            close=100.0,
            tick_volume=100,
        ),
    ]

    result = None

    for bar in bars:
        detected = detector.process(bar)

        if detected is not None:
            result = detected

    assert result is not None
    assert result.swing_type is SwingType.LOW
    assert result.price == 95.0
    assert detector.get_last_swing() == result


def test_duplicate_swing_is_not_reported_twice() -> None:
    """
    Processing the same pivot twice should not create duplicate
    confirmed swings.
    """

    config = SwingDetectorConfig(
        pivot_left=1,
        pivot_right=1,
        atr_validation=False,
        minimum_swing_distance=0.0,
    )

    detector = SwingDetector(config)

    bars = [
        MarketBar(
            timestamp=datetime.now(UTC),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            tick_volume=100,
        ),
        MarketBar(
            timestamp=datetime.now(UTC),
            open=101.0,
            high=105.0,
            low=100.0,
            close=104.0,
            tick_volume=100,
        ),
        MarketBar(
            timestamp=datetime.now(UTC),
            open=100.0,
            high=102.0,
            low=99.0,
            close=100.0,
            tick_volume=100,
        ),
    ]

    first_detection = None

    for bar in bars:
        detected = detector.process(bar)
        if detected is not None:
            first_detection = detected

    assert first_detection is not None
    assert len(detector.get_swings()) == 1

    # Feed additional bars that should not reconfirm
    # the already confirmed swing.
    detector.process(
        MarketBar(
            timestamp=datetime.now(UTC),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            tick_volume=100,
        )
    )

    detector.process(
        MarketBar(
            timestamp=datetime.now(UTC),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            tick_volume=100,
        )
    )

    assert len(detector.get_swings()) == 1


def test_detector_enforces_alternating_swing_sequence() -> None:
    """
    Consecutive confirmed swings should alternate between
    highs and lows.
    """

    config = SwingDetectorConfig(
        pivot_left=1,
        pivot_right=1,
        atr_validation=False,
        minimum_swing_distance=0.0,
    )

    detector = SwingDetector(config)

    # First confirmed swing (HIGH)
    high_bars = [
        MarketBar(datetime.now(UTC), 100, 101, 99, 100, 100),
        MarketBar(datetime.now(UTC), 101, 105, 100, 104, 100),
        MarketBar(datetime.now(UTC), 100, 102, 99, 100, 100),
    ]

    for bar in high_bars:
        detector.process(bar)

    assert len(detector.get_swings()) == 1
    assert detector.get_last_swing().swing_type is SwingType.HIGH

    # Attempt to create another HIGH immediately.
    second_high = [
        MarketBar(datetime.now(UTC), 101, 102, 100, 101, 100),
        MarketBar(datetime.now(UTC), 102, 106, 101, 105, 100),
        MarketBar(datetime.now(UTC), 101, 103, 100, 101, 100),
    ]

    for bar in second_high:
        detector.process(bar)

    swings = detector.get_swings()

    assert len(swings) == 1
    assert swings[0].swing_type is SwingType.HIGH


def test_minimum_swing_distance_is_enforced() -> None:
    """
    Swings smaller than the configured minimum distance
    should be rejected.
    """

    config = SwingDetectorConfig(
        pivot_left=1,
        pivot_right=1,
        atr_validation=False,
        minimum_swing_distance=10.0,
    )

    detector = SwingDetector(config)

    # First valid HIGH
    first_sequence = [
        MarketBar(datetime.now(UTC), 100, 110, 99, 105, 100),
        MarketBar(datetime.now(UTC), 105, 120, 104, 118, 100),
        MarketBar(datetime.now(UTC), 110, 111, 109, 110, 100),
    ]

    for bar in first_sequence:
        detector.process(bar)

    assert len(detector.get_swings()) == 1

    # LOW only 5 points below previous HIGH.
    second_sequence = [
        MarketBar(datetime.now(UTC), 110, 111, 108, 109, 100),
        MarketBar(datetime.now(UTC), 109, 110, 115, 109, 100),
        MarketBar(datetime.now(UTC), 110, 111, 109, 110, 100),
    ]

    for bar in second_sequence:
        detector.process(bar)

    # Detector should reject the second swing.
    assert len(detector.get_swings()) == 1

def test_atr_validation_rejects_small_swings() -> None:
    """
    ATR validation should reject swings that do not satisfy
    the configured ATR threshold.
    """

    config = SwingDetectorConfig(
        pivot_left=1,
        pivot_right=1,
        atr_validation=True,
        atr_period=2,
        atr_multiplier=5.0,
        minimum_swing_distance=0.0,
    )

    detector = SwingDetector(config)

    bars = [
        MarketBar(datetime.now(UTC), 100, 101, 99, 100, 100),
        MarketBar(datetime.now(UTC), 100, 105, 99, 104, 100),
        MarketBar(datetime.now(UTC), 100, 101, 99, 100, 100),
        MarketBar(datetime.now(UTC), 100, 101, 99, 100, 100),
    ]

    detections = []

    for bar in bars:
        swing = detector.process(bar)

        if swing is not None:
            detections.append(swing)

    assert len(detections) == 0

def test_equal_high_tolerance_allows_equal_highs() -> None:
    """
    Equal highs within the configured tolerance should not
    produce a confirmed swing high.
    """

    config = SwingDetectorConfig(
        pivot_left=1,
        pivot_right=1,
        equal_high_tolerance=0.5,
        atr_validation=False,
        minimum_swing_distance=0.0,
    )

    detector = SwingDetector(config)

    bars = [
        MarketBar(datetime.now(UTC), 100, 105.0, 99, 100, 100),
        MarketBar(datetime.now(UTC), 101, 105.3, 100, 104, 100),
        MarketBar(datetime.now(UTC), 100, 105.0, 99, 100, 100),
    ]

    results = []

    for bar in bars:
        swing = detector.process(bar)

        if swing is not None:
            results.append(swing)

    assert len(results) == 0


def test_equal_low_tolerance_allows_equal_lows() -> None:
    """
    Equal lows within the configured tolerance should not
    produce a confirmed swing low.
    """

    config = SwingDetectorConfig(
        pivot_left=1,
        pivot_right=1,
        equal_low_tolerance=0.5,
        atr_validation=False,
        minimum_swing_distance=0.0,
    )

    detector = SwingDetector(config)

    bars = [
        MarketBar(
            datetime.now(UTC),
            100,
            101,
            95.0,
            100,
            100,
        ),
        MarketBar(
            datetime.now(UTC),
            100,
            101,
            94.7,
            100,
            100,
        ),
        MarketBar(
            datetime.now(UTC),
            100,
            101,
            95.0,
            100,
            100,
        ),
    ]

    results = []

    for bar in bars:
        swing = detector.process(bar)

        if swing is not None:
            results.append(swing)

    assert len(results) == 0


def test_public_api_returns_expected_state() -> None:
    """
    The public API should expose the detector state without
    allowing callers to modify the detector's internal collections.
    """

    config = SwingDetectorConfig(
        pivot_left=1,
        pivot_right=1,
        atr_validation=False,
        minimum_swing_distance=0.0,
    )

    detector = SwingDetector(config)

    bars = [
        MarketBar(datetime.now(UTC), 100, 101, 99, 100, 100),
        MarketBar(datetime.now(UTC), 101, 105, 100, 104, 100),
        MarketBar(datetime.now(UTC), 100, 102, 99, 100, 100),
    ]

    for bar in bars:
        detector.process(bar)

    last_swing = detector.get_last_swing()
    swings = detector.get_swings()
    state = detector.get_state()

    assert last_swing is not None
    assert len(swings) == 1
    assert swings[0] == last_swing
    assert state.last_swing == last_swing
    assert tuple(state.confirmed_swings) == swings