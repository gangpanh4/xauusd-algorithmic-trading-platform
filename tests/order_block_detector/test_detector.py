"""
Unit tests for the Order Block Detection Engine.
"""

from __future__ import annotations

from core.order_block_detector.config import (
    OrderBlockDetectorConfig,
)
from core.order_block_detector.detector import (
    OrderBlockDetector,
)


def test_detector_initializes_with_default_config() -> None:
    """
    Detector should initialize with the default configuration.
    """

    detector = OrderBlockDetector()

    assert isinstance(
        detector.config,
        OrderBlockDetectorConfig,
    )

    assert detector.state.confirmed_order_blocks == []
    assert detector.state.active_order_blocks == []
    assert detector.state.mitigated_order_blocks == []
    assert detector.state.invalidated_order_blocks == []
    assert detector.state.expired_order_blocks == []
    assert detector.state.confirmed_events == []
    assert detector.state.last_event is None
    assert detector.state.processed_break_count == 0
    assert detector.state.next_block_id == 1


def test_reset_clears_runtime_state() -> None:
    """
    Reset should restore the detector state.
    """

    detector = OrderBlockDetector()

    detector.state.processed_break_count = 10
    detector.state.next_block_id = 5

    detector.reset()

    assert detector.state.confirmed_order_blocks == []
    assert detector.state.active_order_blocks == []
    assert detector.state.mitigated_order_blocks == []
    assert detector.state.invalidated_order_blocks == []
    assert detector.state.expired_order_blocks == []
    assert detector.state.confirmed_events == []
    assert detector.state.last_event is None
    assert detector.state.processed_break_count == 0
    assert detector.state.next_block_id == 1


def test_get_state_returns_runtime_state() -> None:
    """
    get_state should return the detector runtime state.
    """

    detector = OrderBlockDetector()

    assert detector.get_state() is detector.state


def test_get_order_blocks_returns_confirmed_blocks() -> None:
    """
    get_order_blocks should return confirmed Order Blocks.
    """

    detector = OrderBlockDetector()

    assert detector.get_order_blocks() == []


def test_get_active_order_blocks_returns_active_blocks() -> None:
    """
    get_active_order_blocks should return active Order Blocks.
    """

    detector = OrderBlockDetector()

    assert detector.get_active_order_blocks() == []


def test_get_last_event_returns_none_initially() -> None:
    """
    No Order Block event should exist after initialization.
    """

    detector = OrderBlockDetector()

    assert detector.get_last_event() is None


def test_process_increments_processed_break_count() -> None:
    """
    Version 1 detector should count processed breaks even though
    no Order Block detection is implemented yet.
    """

    detector = OrderBlockDetector()

    assert detector.state.processed_break_count == 0

    result = detector.process(
        break_event=None,      # type: ignore[arg-type]
        liquidity_event=None,
    )

    assert result is None

    assert detector.state.processed_break_count == 1