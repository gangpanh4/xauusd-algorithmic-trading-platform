"""
Runtime state for the Swing Detection Engine.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque

from core.data.market_data import MarketBar
from core.market_structure.enums import DetectorStatus
from core.market_structure.models import (
    BOSEvent,
    SwingPoint,
)


@dataclass(slots=True)
class SwingDetectorState:
    """
    Mutable runtime state owned exclusively by the SwingDetector.

    This class stores the rolling market history and detector state
    required for streaming swing detection. It contains no detection
    logic.
    """

    # Rolling history of recently processed bars.
    recent_bars: Deque[MarketBar] = field(default_factory=deque)

    # Candidate pivot currently awaiting confirmation.
    pending_pivot: MarketBar | None = None

    # Confirmed swing history.
    confirmed_swings: list[SwingPoint] = field(default_factory=list)

    # Most recently confirmed swing.
    last_swing: SwingPoint | None = None

    # Human-readable detector status.
    # Allowed values:
    # WAITING
    # RUNNING
    # BREAK_CONFIRMED
    detector_status: DetectorStatus = DetectorStatus.WAITING

    # Total number of processed bars.
    processed_bar_count: int = 0

    def reset(self) -> None:
        """
        Reset the detector state.
        """

        self.recent_bars.clear()
        self.pending_pivot = None
        self.confirmed_swings.clear()
        self.last_swing = None
        self.detector_status = DetectorStatus.WAITING
        self.processed_bar_count = 0


@dataclass(slots=True)
class BOSDetectorState:
    """
    Mutable runtime state owned exclusively by the BOSDetector.

    This class stores the confirmed swings and confirmed structural
    breaks detected during streaming analysis. It contains no
    detection logic.
    """

    # Confirmed swings received by the BOS detector.
    confirmed_swings: list[SwingPoint] = field(default_factory=list)

    # Confirmed BOS history.
    confirmed_breaks: list[BOSEvent] = field(default_factory=list)

    # Most recently confirmed BOS.
    last_break: BOSEvent | None = None

    # Human-readable detector status.
    # Allowed values:
    # WAITING
    # RUNNING
    # BREAK_CONFIRMED
    detector_status: DetectorStatus = DetectorStatus.WAITING

    # Total number of processed swings.
    processed_swing_count: int = 0

    def reset(self) -> None:
        """
        Reset the detector state.
        """

        self.confirmed_swings.clear()
        self.confirmed_breaks.clear()
        self.last_break = None
        self.detector_status = DetectorStatus.WAITING
        self.processed_swing_count = 0