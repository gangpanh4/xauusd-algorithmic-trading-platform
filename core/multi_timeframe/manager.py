"""
Multi-Timeframe manager.

Coordinates analysis state for all configured timeframes.
"""

from __future__ import annotations

from datetime import datetime

from .config import MultiTimeframeConfig
from .enums import Timeframe
from .models import TimeframeState
from .state import MultiTimeframeState


class MultiTimeframeManager:
    """
    Coordinates all timeframe analyses.

    This class owns the runtime state for every active
    timeframe. It does not perform market analysis itself;
    it stores and synchronizes results produced by the
    MarketStructureEngine, PriceActionEngine, and future
    analysis engines.
    """

    def __init__(
        self,
        config: MultiTimeframeConfig | None = None,
    ) -> None:

        self.config = config or MultiTimeframeConfig()

        self.state = MultiTimeframeState()

    def reset(
        self,
    ) -> None:
        """
        Reset runtime state.
        """

        self.state.reset()

    def update(
        self,
        timeframe: Timeframe,
        analysis: TimeframeState,
    ) -> None:
        """
        Store the latest analysis for one timeframe.
        """

        previous = self.state.timeframe_states.get(timeframe)

        if previous is not None:
            self.state.previous_states[timeframe] = previous

        self.state.timeframe_states[timeframe] = analysis

        self.state.processed_updates += 1

        self.state.last_updated = datetime.utcnow()

        self.state.initialized = True

    def get_state(
        self,
        timeframe: Timeframe,
    ) -> TimeframeState | None:
        """
        Return the latest analysis for one timeframe.
        """

        return self.state.timeframe_states.get(timeframe)

    def has_state(
        self,
        timeframe: Timeframe,
    ) -> bool:
        """
        Check whether analysis exists.
        """

        return timeframe in self.state.timeframe_states

    def is_ready(
        self,
    ) -> bool:
        """
        True when every configured timeframe has
        completed analysis.
        """

        return all(
            timeframe in self.state.timeframe_states
            for timeframe in self.config.active_timeframes
        )