"""Backtest-safe adapter for observational strategy evaluation.

This adapter consumes synchronized completed-bar multi-timeframe results and
records strategy observations without opening trades or mutating the active
trading pipeline.
"""

from __future__ import annotations

from datetime import UTC, datetime

from core.data.models import MarketBar
from core.multi_timeframe.models import MultiTimeframeResult
from core.strategies import (
    StrategyContext,
    StrategyObservation,
    XAUUSDBOSCHOCHStrategy,
)


class BacktestStrategyObserver:
    """Run the observational strategy on strictly ordered M5 closes."""

    def __init__(
        self,
        strategy: XAUUSDBOSCHOCHStrategy | None = None,
    ) -> None:
        self.strategy = strategy or XAUUSDBOSCHOCHStrategy()
        self._last_timestamp: datetime | None = None
        self._last_bar_index: int | None = None

    def reset(self) -> None:
        """Reset chronology and all owned strategy lifecycle state."""

        self.strategy.reset()
        self._last_timestamp = None
        self._last_bar_index = None

    def observe(
        self,
        *,
        multi_timeframe: MultiTimeframeResult,
        current_bar: MarketBar,
        current_bar_index: int,
    ) -> StrategyObservation:
        """Observe one completed M5 bar using synchronized MTF facts.

        Duplicate or decreasing timestamps and bar indexes are rejected. This
        protects stateful strategy logic from replaying the same historical
        observation and preserves deterministic backtest chronology.
        """

        if not isinstance(multi_timeframe, MultiTimeframeResult):
            raise TypeError('multi_timeframe must be MultiTimeframeResult')
        if not isinstance(current_bar, MarketBar):
            raise TypeError('current_bar must be MarketBar')
        if isinstance(current_bar_index, bool) or not isinstance(
            current_bar_index,
            int,
        ):
            raise TypeError('current_bar_index must be an integer')
        if current_bar_index < 0:
            raise ValueError('current_bar_index cannot be negative')

        timestamp = current_bar.timestamp.astimezone(UTC)
        if self._last_timestamp is not None and timestamp <= self._last_timestamp:
            raise ValueError(
                'strategy observation timestamps must be strictly increasing'
            )
        if (
            self._last_bar_index is not None
            and current_bar_index <= self._last_bar_index
        ):
            raise ValueError(
                'strategy observation bar indexes must be strictly increasing'
            )

        observation = self.strategy.observe(
            StrategyContext(
                multi_timeframe=multi_timeframe,
                current_bar=current_bar,
                current_bar_index=current_bar_index,
            )
        )
        self._last_timestamp = timestamp
        self._last_bar_index = current_bar_index
        return observation

    @property
    def observations(self) -> tuple[StrategyObservation, ...]:
        """Return immutable chronological strategy observations."""

        return tuple(self.strategy.state.observations)

    def observation_summary(self) -> dict[str, int]:
        """Return counts grouped by strategy reason code."""

        return self.strategy.state.observation_summary()

    @property
    def candidate_count(self) -> int:
        """Return observational candidates without authorizing execution."""

        return sum(
            observation.candidate_trade is not None
            for observation in self.strategy.state.observations
        )
