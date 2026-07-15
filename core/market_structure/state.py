"""
Runtime state for the Market Structure Engine.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque

from core.data.market_data import MarketBar
from core.market_structure.enums import (
    DetectorStatus,
    MarketTrend,
)
from core.market_structure.models import (
    BOSEvent,
    CHOCHEvent,
    LiquidityLevel,
    LiquiditySweepEvent,
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

    # Current confirmed market trend.
    current_trend: MarketTrend = MarketTrend.UNKNOWN

    # Swing currently protected by the active trend.
    protected_swing: SwingPoint | None = None

    # Human-readable detector status.
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
        self.current_trend = MarketTrend.UNKNOWN
        self.protected_swing = None
        self.detector_status = DetectorStatus.WAITING
        self.processed_swing_count = 0


@dataclass(slots=True)
class CHOCHDetectorState:
    """
    Mutable runtime state owned exclusively by the CHOCHDetector.

    This class stores the confirmed Change of Character (CHOCH)
    events detected during streaming analysis. It contains no
    detection logic.
    """

    # Confirmed swings received by the CHOCH detector.
    confirmed_swings: list[SwingPoint] = field(default_factory=list)

    # Confirmed CHOCH history.
    confirmed_changes: list[CHOCHEvent] = field(default_factory=list)

    # Most recently confirmed CHOCH.
    last_change: CHOCHEvent | None = None

    # Human-readable detector status.
    detector_status: DetectorStatus = DetectorStatus.WAITING

    # Total number of processed swings.
    processed_swing_count: int = 0

    def reset(self) -> None:
        """
        Reset the detector state.
        """

        self.confirmed_swings.clear()
        self.confirmed_changes.clear()
        self.last_change = None
        self.detector_status = DetectorStatus.WAITING
        self.processed_swing_count = 0

@dataclass(slots=True)
class LiquidityDetectorState:
    """
    Mutable runtime state owned exclusively by the LiquidityDetector.

    This class stores tracked liquidity levels and confirmed
    liquidity sweep events. It contains no detection logic.
    """

    # Known liquidity pools.
    liquidity_levels: list[LiquidityLevel] = field(
        default_factory=list
    )

    # Confirmed liquidity sweeps.
    confirmed_sweeps: list[LiquiditySweepEvent] = field(
        default_factory=list
    )

    # Most recently confirmed sweep.
    last_sweep: LiquiditySweepEvent | None = None

    # Human-readable detector status.
    detector_status: DetectorStatus = DetectorStatus.WAITING

    # Total number of processed swings.
    processed_swing_count: int = 0

    def reset(self) -> None:
        """
        Reset the detector state.
        """

        self.liquidity_levels.clear()
        self.confirmed_sweeps.clear()
        self.last_sweep = None
        self.detector_status = DetectorStatus.WAITING
        self.processed_swing_count = 0