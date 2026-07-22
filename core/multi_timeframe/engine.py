"""Multi-timeframe result aggregation."""

from __future__ import annotations

from datetime import UTC, datetime
from math import isfinite

from .config import MultiTimeframeConfig
from .enums import MarketBias, Timeframe, TimeframeAlignment
from .manager import MultiTimeframeManager
from .models import MultiTimeframeResult, TimeframeState


class MultiTimeframeEngine:
    """Combine validated timeframe snapshots into one aggregate result."""

    _REQUIRED_RESULT_TIMEFRAMES: tuple[Timeframe, ...] = (
        Timeframe.WEEKLY,
        Timeframe.DAILY,
        Timeframe.H4,
        Timeframe.H1,
        Timeframe.M15,
        Timeframe.M5,
    )

    def __init__(
        self,
        config: MultiTimeframeConfig | None = None,
    ) -> None:
        self.config = config or MultiTimeframeConfig()
        self._validate_config()

    def process(
        self,
        manager: MultiTimeframeManager,
    ) -> MultiTimeframeResult:
        """Combine one complete, synchronized manager snapshot.

        The result timestamp is the newest completed timeframe timestamp in the
        supplied snapshot. Wall-clock time is deliberately not used because it
        makes historical backtests non-deterministic and mixes observation time
        with computation time.
        """
        if not isinstance(manager, MultiTimeframeManager):
            raise TypeError("manager must be a MultiTimeframeManager")

        self._validate_manager_contract(manager)

        if not manager.is_ready():
            raise RuntimeError(
                "MultiTimeframeManager is not fully initialized."
            )

        states_by_timeframe = {
            timeframe: self._require_state(manager, timeframe)
            for timeframe in self._REQUIRED_RESULT_TIMEFRAMES
        }
        states = tuple(states_by_timeframe.values())

        confidence = self._calculate_confidence(states)
        overall_bias = self._calculate_bias(states)
        overall_alignment = self._calculate_alignment(states)
        result_timestamp = self._newest_snapshot_timestamp(states)

        result = MultiTimeframeResult(
            weekly=states_by_timeframe[Timeframe.WEEKLY],
            daily=states_by_timeframe[Timeframe.DAILY],
            h4=states_by_timeframe[Timeframe.H4],
            h1=states_by_timeframe[Timeframe.H1],
            m15=states_by_timeframe[Timeframe.M15],
            m5=states_by_timeframe[Timeframe.M5],
            overall_bias=overall_bias,
            overall_alignment=overall_alignment,
            confidence=confidence,
            timestamp=result_timestamp,
        )

        # Commit only after the complete aggregate has been calculated and
        # validated successfully.
        manager.state.latest_result = result
        return result

    def _validate_config(self) -> None:
        active = self.config.active_timeframes
        hierarchy = self.config.hierarchy

        if not active:
            raise ValueError("active_timeframes must not be empty")
        if len(set(active)) != len(active):
            raise ValueError("active_timeframes must not contain duplicates")
        if any(not isinstance(value, Timeframe) for value in active):
            raise TypeError("active_timeframes must contain Timeframe values")

        if len(hierarchy) != len(self._REQUIRED_RESULT_TIMEFRAMES):
            raise ValueError(
                "hierarchy must contain exactly W1, D1, H4, H1, M15, and M5"
            )
        if tuple(hierarchy) != self._REQUIRED_RESULT_TIMEFRAMES:
            raise ValueError(
                "hierarchy must be ordered W1, D1, H4, H1, M15, M5"
            )
        if tuple(active) != self._REQUIRED_RESULT_TIMEFRAMES:
            raise ValueError(
                "active_timeframes must contain W1, D1, H4, H1, M15, and M5 "
                "in hierarchy order"
            )

    def _validate_manager_contract(
        self,
        manager: MultiTimeframeManager,
    ) -> None:
        if tuple(manager.config.active_timeframes) != tuple(
            self.config.active_timeframes
        ):
            raise ValueError(
                "manager and engine active_timeframes must match"
            )
        if tuple(manager.config.hierarchy) != tuple(self.config.hierarchy):
            raise ValueError("manager and engine hierarchy must match")

    @staticmethod
    def _require_state(
        manager: MultiTimeframeManager,
        timeframe: Timeframe,
    ) -> TimeframeState:
        state = manager.get_state(timeframe)
        if state is None:
            raise RuntimeError(
                f"Missing required timeframe state: {timeframe.value}"
            )
        if not isinstance(state, TimeframeState):
            raise TypeError(
                f"State for {timeframe.value} must be a TimeframeState"
            )
        if state.timeframe is not timeframe:
            raise ValueError(
                f"State key {timeframe.value} does not match "
                f"analysis timeframe {state.timeframe.value}"
            )
        if not isfinite(state.confidence):
            raise ValueError(
                f"Confidence for {timeframe.value} must be finite"
            )
        if not 0.0 <= state.confidence <= 1.0:
            raise ValueError(
                f"Confidence for {timeframe.value} must be between 0 and 1"
            )
        if state.timestamp is None:
            raise ValueError(
                f"State timestamp for {timeframe.value} must not be None"
            )
        MultiTimeframeEngine._require_aware_datetime(
            state.timestamp,
            field_name=f"timestamp for {timeframe.value}",
        )
        return state

    @staticmethod
    def _calculate_confidence(
        states: tuple[TimeframeState, ...],
    ) -> float:
        return sum(state.confidence for state in states) / len(states)

    @staticmethod
    def _calculate_bias(
        states: tuple[TimeframeState, ...],
    ) -> MarketBias:
        bullish = sum(
            state.bias is MarketBias.BULLISH
            for state in states
        )
        bearish = sum(
            state.bias is MarketBias.BEARISH
            for state in states
        )

        if bullish > bearish:
            return MarketBias.BULLISH
        if bearish > bullish:
            return MarketBias.BEARISH
        return MarketBias.NEUTRAL

    @staticmethod
    def _calculate_alignment(
        states: tuple[TimeframeState, ...],
    ) -> TimeframeAlignment:
        aligned = sum(
            state.alignment is TimeframeAlignment.ALIGNED
            for state in states
        )

        if aligned == len(states):
            return TimeframeAlignment.ALIGNED
        if aligned >= len(states) // 2:
            return TimeframeAlignment.PARTIAL
        return TimeframeAlignment.CONFLICT

    @staticmethod
    def _newest_snapshot_timestamp(
        states: tuple[TimeframeState, ...],
    ) -> datetime:
        timestamps = tuple(
            state.timestamp.astimezone(UTC)
            for state in states
            if state.timestamp is not None
        )
        if len(timestamps) != len(states):
            raise ValueError(
                "Every timeframe state must have a completed-bar timestamp"
            )
        return max(timestamps)

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
