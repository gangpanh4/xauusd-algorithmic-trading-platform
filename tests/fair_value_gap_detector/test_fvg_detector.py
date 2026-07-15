"""
Unit tests for the Fair Value Gap detector.
"""

from __future__ import annotations

from datetime import datetime, timezone

from core.data.models import MarketBar
from core.fair_value_gap_detector.detector import (
    FairValueGapDetector,
)
from core.fair_value_gap_detector.models import (
    FairValueGapType,
)


def make_bar(
    *,
    open: float,
    high: float,
    low: float,
    close: float,
) -> MarketBar:
    """
    Create a MarketBar for testing.
    """

    return MarketBar(
        timestamp=datetime.now(timezone.utc),
        open=open,
        high=high,
        low=low,
        close=close,
        tick_volume=100,
    )


def test_detector_initializes() -> None:
    """
    Detector should initialize correctly.
    """

    detector = FairValueGapDetector()

    assert detector.state.pending_candidates == []
    assert detector.state.processed_count == 0


def test_reset() -> None:
    """
    Reset should clear runtime state.
    """

    detector = FairValueGapDetector()

    detector.state.processed_count = 5

    detector.reset()

    assert detector.state.processed_count == 0
    assert detector.state.pending_candidates == []


def test_requires_three_bars() -> None:
    """
    Less than three bars should produce no FVG.
    """

    detector = FairValueGapDetector()

    result = detector.process([])

    assert result is None


def test_detects_bullish_fvg() -> None:
    """
    Detect a bullish Fair Value Gap.
    """

    detector = FairValueGapDetector()

    bars = [
        make_bar(
            open=100,
            high=101,
            low=99,
            close=100,
        ),
        make_bar(
            open=101,
            high=104,
            low=101,
            close=104,
        ),
        make_bar(
            open=105,
            high=106,
            low=103,
            close=105,
        ),
    ]

    candidate = detector.process(bars)

    assert candidate is not None
    assert candidate.gap_type == FairValueGapType.BULLISH


def test_detects_bearish_fvg() -> None:
    """
    Detect a bearish Fair Value Gap.
    """

    detector = FairValueGapDetector()

    bars = [
        make_bar(
            open=105,
            high=106,
            low=104,
            close=105,
        ),
        make_bar(
            open=103,
            high=104,
            low=101,
            close=101,
        ),
        make_bar(
            open=99,
            high=100,
            low=98,
            close=99,
        ),
    ]

    candidate = detector.process(bars)

    assert candidate is not None
    assert candidate.gap_type == FairValueGapType.BEARISH


def test_no_gap_returns_none() -> None:
    """
    Overlapping candles should not create an FVG.
    """

    detector = FairValueGapDetector()

    bars = [
        make_bar(
            open=100,
            high=102,
            low=99,
            close=101,
        ),
        make_bar(
            open=101,
            high=103,
            low=100,
            close=102,
        ),
        make_bar(
            open=102,
            high=103,
            low=101,
            close=102,
        ),
    ]

    candidate = detector.process(bars)

    assert candidate is None