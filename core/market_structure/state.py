"""
Runtime state for the Swing Detection Engine.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque

from core.data.market_data import MarketBar
from core.market_structure.models import SwingPoint


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
    detector_status: str = "WAITING"

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
        self.detector_status = "WAITING"
        self.processed_bar_count = 0