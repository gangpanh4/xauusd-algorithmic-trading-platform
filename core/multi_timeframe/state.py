"""
Multi-Timeframe runtime state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .enums import (
    Timeframe,
)
from .models import (
    MultiTimeframeResult,
    TimeframeState,
)


@dataclass(slots=True)
class MultiTimeframeState:
    """
    Runtime state for the Multi-Timeframe Engine.
    """

    # -------------------------------------------------
    # Latest analysis for each timeframe
    # -------------------------------------------------

    timeframe_states: dict[
        Timeframe,
        TimeframeState,
    ] = field(default_factory=dict)

    # -------------------------------------------------
    # Previous analysis
    # Used to detect meaningful changes.
    # -------------------------------------------------

    previous_states: dict[
        Timeframe,
        TimeframeState,
    ] = field(default_factory=dict)

    # -------------------------------------------------
    # Latest combined result
    # -------------------------------------------------

    latest_result: MultiTimeframeResult | None = None

    # -------------------------------------------------
    # Runtime statistics
    # -------------------------------------------------

    processed_updates: int = 0

    last_updated: datetime | None = None

    initialized: bool = False

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------

    def reset(self) -> None:
        """
        Reset runtime state.
        """

        self.timeframe_states.clear()

        self.previous_states.clear()

        self.latest_result = None

        self.processed_updates = 0

        self.last_updated = None

        self.initialized = False