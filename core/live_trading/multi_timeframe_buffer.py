"""Completed-bar multi-timeframe history for live analysis."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from types import MappingProxyType

from core.data.models import MarketBar
from core.multi_timeframe.enums import Timeframe
from core.multi_timeframe.history_alignment import (
    completed_period_buckets,
    normalize_utc,
    visible_bars,
)


class LiveMultiTimeframeBuffer:
    """Own synchronized completed M5/M15/H1/H4 histories for live analysis."""

    _BASE_TIMEFRAMES = (
        Timeframe.M5,
        Timeframe.M15,
        Timeframe.H1,
        Timeframe.H4,
    )
    def __init__(
        self,
        window_bars: int = 500,
        *,
        source_capacity_bars: Mapping[Timeframe, int] | None = None,
    ) -> None:
        if isinstance(window_bars, bool) or not isinstance(window_bars, int):
            raise TypeError("window_bars must be an integer")
        if window_bars < 2:
            raise ValueError("window_bars must be at least 2")

        self.window_bars = window_bars
        self._source_capacity_bars = self._validate_capacities(
            source_capacity_bars
        )
        self._bars: dict[Timeframe, list[MarketBar]] = {
            timeframe: [] for timeframe in self._BASE_TIMEFRAMES
        }

    @property
    def histories(self) -> Mapping[Timeframe, tuple[MarketBar, ...]]:
        """Return immutable base-timeframe histories."""

        return MappingProxyType(
            {
                timeframe: tuple(bars)
                for timeframe, bars in self._bars.items()
            }
        )

    def reset(self) -> None:
        """Clear all owned histories."""

        for bars in self._bars.values():
            bars.clear()

    def load(
        self,
        timeframe: Timeframe,
        bars: Sequence[MarketBar],
    ) -> None:
        """Replace one base-timeframe history with validated completed bars."""

        self._require_base_timeframe(timeframe)
        validated = list(bars)
        self._validate_chronology(validated)
        capacity = self._source_capacity_bars[timeframe]
        self._bars[timeframe] = validated[-capacity:]

    def append(self, timeframe: Timeframe, bar: MarketBar) -> bool:
        """Append one completed bar, returning False for an exact duplicate."""

        self._require_base_timeframe(timeframe)
        self._validate_bar(bar)

        history = self._bars[timeframe]
        if history:
            latest = history[-1]
            if bar.timestamp == latest.timestamp:
                if bar == latest:
                    return False
                raise ValueError(
                    f"Revised completed {timeframe.value} bar received for "
                    f"{bar.timestamp.isoformat()}."
                )
            if bar.timestamp < latest.timestamp:
                raise ValueError(
                    f"{timeframe.value} timestamps must increase strictly."
                )

        history.append(bar)
        capacity = self._source_capacity_bars[timeframe]
        if len(history) > capacity:
            del history[: len(history) - capacity]
        return True

    def snapshot(
        self,
        boundary: datetime,
    ) -> Mapping[Timeframe, tuple[MarketBar, ...]] | None:
        """Return the completed six-timeframe snapshot visible at boundary."""

        boundary = self._normalize_boundary(boundary)
        visible: dict[Timeframe, tuple[MarketBar, ...]] = {}

        for timeframe in self._BASE_TIMEFRAMES:
            values = visible_bars(
                self._bars[timeframe],
                timeframe=timeframe,
                boundary=boundary,
                window_bars=self.window_bars,
            )
            if len(values) < self.window_bars:
                return None
            visible[timeframe] = values

        h4_values = visible[Timeframe.H4]
        daily = self._aggregate_completed(
            h4_values,
            boundary=boundary,
            weekly=False,
        )
        weekly = self._aggregate_completed(
            h4_values,
            boundary=boundary,
            weekly=True,
        )
        if not daily or not weekly:
            return None

        return MappingProxyType(
            {
                Timeframe.WEEKLY: weekly[-self.window_bars :],
                Timeframe.DAILY: daily[-self.window_bars :],
                Timeframe.H4: visible[Timeframe.H4],
                Timeframe.H1: visible[Timeframe.H1],
                Timeframe.M15: visible[Timeframe.M15],
                Timeframe.M5: visible[Timeframe.M5],
            }
        )

    @staticmethod
    def _aggregate_completed(
        bars: Sequence[MarketBar],
        *,
        boundary: datetime,
        weekly: bool,
    ) -> tuple[MarketBar, ...]:
        return tuple(
                MarketBar(
                    timestamp=start,
                    open=float(values[0].open),
                    high=max(float(item.high) for item in values),
                    low=min(float(item.low) for item in values),
                    close=float(values[-1].close),
                    tick_volume=sum(int(item.tick_volume) for item in values),
                )
            for start, values in completed_period_buckets(
                bars,
                boundary=boundary,
                weekly=weekly,
            )
        )

    @classmethod
    def _validate_chronology(cls, bars: Sequence[MarketBar]) -> None:
        previous: datetime | None = None
        for bar in bars:
            cls._validate_bar(bar)
            if previous is not None and bar.timestamp <= previous:
                raise ValueError(
                    "Historical bars must be strictly increasing without "
                    "duplicate timestamps."
                )
            previous = bar.timestamp

    @staticmethod
    def _validate_bar(bar: MarketBar) -> None:
        if not isinstance(bar, MarketBar):
            raise TypeError("bar must be core.data.models.MarketBar")
        if bar.timestamp.tzinfo is None or bar.timestamp.utcoffset() is None:
            raise ValueError("bar timestamp must be timezone-aware")

    @classmethod
    def _require_base_timeframe(cls, timeframe: Timeframe) -> None:
        if timeframe not in cls._BASE_TIMEFRAMES:
            raise ValueError(
                "Live buffer accepts only M5, M15, H1, and H4 source bars."
            )

    @staticmethod
    def _normalize_boundary(boundary: datetime) -> datetime:
        return normalize_utc(boundary, "boundary")

    def _validate_capacities(
        self,
        values: Mapping[Timeframe, int] | None,
    ) -> Mapping[Timeframe, int]:
        if values is None:
            return MappingProxyType(
                {timeframe: self.window_bars for timeframe in self._BASE_TIMEFRAMES}
            )
        if not isinstance(values, Mapping):
            raise TypeError("source_capacity_bars must be a mapping or None")
        missing = set(self._BASE_TIMEFRAMES).difference(values)
        unexpected = set(values).difference(self._BASE_TIMEFRAMES)
        if missing or unexpected:
            raise ValueError(
                "source_capacity_bars must contain exactly M5, M15, H1, and H4"
            )
        validated: dict[Timeframe, int] = {}
        for timeframe in self._BASE_TIMEFRAMES:
            capacity = values[timeframe]
            if isinstance(capacity, bool) or not isinstance(capacity, int):
                raise TypeError("source capacities must be integers")
            if capacity < self.window_bars:
                raise ValueError(
                    "source capacities must be at least window_bars"
                )
            validated[timeframe] = capacity
        return MappingProxyType(validated)
