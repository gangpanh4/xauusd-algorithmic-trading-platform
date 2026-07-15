"""
Regression tests for the public Order Block API.
"""

from __future__ import annotations

from core.order_block_detector import (
    OrderBlockDetector,
)


def test_detector_can_be_constructed() -> None:
    """
    The detector should be constructible through the
    package public API.
    """

    detector = OrderBlockDetector()

    assert detector is not None


def test_detector_exposes_runtime_state() -> None:
    """
    The detector should expose its runtime state.
    """

    detector = OrderBlockDetector()

    assert detector.get_state() is detector.state


def test_detector_starts_with_no_confirmed_blocks() -> None:
    """
    No confirmed Order Blocks should exist after
    initialization.
    """

    detector = OrderBlockDetector()

    assert detector.get_order_blocks() == []


def test_detector_starts_with_no_active_blocks() -> None:
    """
    No active Order Blocks should exist after
    initialization.
    """

    detector = OrderBlockDetector()

    assert detector.get_active_order_blocks() == []