"""
Multi-Timeframe manager.

Coordinates analysis state for all configured timeframes.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from math import isfinite

from .config import MultiTimeframeConfig
from .enums import Timeframe
from .models import TimeframeState
from .state import MultiTimeframeState


UtcClock = Callable[[], datetime]


class MultiTimeframeManager:
    """
    Coordinate and store analysis state for configured timeframes.

    The manager owns no analytical engines. It validates and commits snapshots
    produced elsewhere while preserving the immediately previous snapshot for
    each timeframe.
    """

    def __init__(
        self,
        config: MultiTimeframeConfig | None = None,
        *,
        clock: UtcClock | None = None,
    ) -> None:
        self.config = config or MultiTimeframeConfig()
        self._clock = clock or self._utc_now
        self.state = MultiTimeframeState()

        self._validate_config()
        self._read_clock()

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC)

    def reset(self) -> None:
        """Reset all runtime state."""
        self.state.reset()

    def update(
        self,
        timeframe: Timeframe,
        analysis: TimeframeState,
    ) -> None:
        """
        Atomically store the latest analysis for one active timeframe.

        Validation and timestamp acquisition complete before any state is
        mutated. A failed update therefore cannot partially replace a previous
        snapshot or increment runtime counters.
        """
        self._validate_update(timeframe, analysis)
        updated_at = self._read_clock()

        previous = self.state.timeframe_states.get(timeframe)
        if previous is not None:
            self.state.previous_states[timeframe] = previous

        self.state.timeframe_states[timeframe] = analysis
        self.state.processed_updates += 1
        self.state.last_updated = updated_at
        self.state.initialized = True

    def get_state(
        self,
        timeframe: Timeframe,
    ) -> TimeframeState | None:
        """Return the latest analysis for one timeframe."""
        self._validate_timeframe(timeframe)
        return self.state.timeframe_states.get(timeframe)

    def has_state(
        self,
        timeframe: Timeframe,
    ) -> bool:
        """Return whether analysis exists for one timeframe."""
        self._validate_timeframe(timeframe)
        return timeframe in self.state.timeframe_states

    def is_ready(self) -> bool:
        """Return whether every configured active timeframe has analysis."""
        return all(
            timeframe in self.state.timeframe_states
            for timeframe in self.config.active_timeframes
        )

    def _validate_config(self) -> None:
        active = self.config.active_timeframes
        if not active:
            raise ValueError("active_timeframes must not be empty")
        if len(set(active)) != len(active):
            raise ValueError("active_timeframes must not contain duplicates")
        if any(not isinstance(item, Timeframe) for item in active):
            raise TypeError("active_timeframes must contain Timeframe values")

    def _validate_update(
        self,
        timeframe: Timeframe,
        analysis: TimeframeState,
    ) -> None:
        self._validate_timeframe(timeframe)

        if timeframe not in self.config.active_timeframes:
            raise ValueError(
                f"timeframe {timeframe.value} is not active in this manager"
            )
        if not isinstance(analysis, TimeframeState):
            raise TypeError("analysis must be a TimeframeState")
        if analysis.timeframe is not timeframe:
            raise ValueError(
                "analysis.timeframe must match the update timeframe"
            )
        if not isfinite(analysis.confidence):
            raise ValueError("analysis.confidence must be finite")
        if not 0.0 <= analysis.confidence <= 1.0:
            raise ValueError("analysis.confidence must be between 0 and 1")
        if analysis.timestamp is not None:
            self._require_aware_datetime(
                analysis.timestamp,
                field_name="analysis.timestamp",
            )

    @staticmethod
    def _validate_timeframe(timeframe: Timeframe) -> None:
        if not isinstance(timeframe, Timeframe):
            raise TypeError("timeframe must be a Timeframe")

    def _read_clock(self) -> datetime:
        value = self._clock()
        self._require_aware_datetime(value, field_name="clock result")
        return value.astimezone(UTC)

    @staticmethod
    def _require_aware_datetime(
        value: datetime,
        *,
        field_name: str,
    ) -> None:
        if not isinstance(value, datetime):
            raise TypeError(f"{field_name} must be a datetime")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field_name} must be timezone-aware")
