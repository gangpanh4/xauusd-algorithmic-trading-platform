"""
Unit tests for the Swing Detection Engine.
"""

from __future__ import annotations

from datetime import UTC, datetime

from core.data.market_data import MarketBar
from core.market_structure.config import SwingDetectorConfig
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