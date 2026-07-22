"""Completed-bar multi-timeframe history for live analysis."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from types import MappingProxyType

from core.data.models import MarketBar
from core.multi_timeframe.enums import Timeframe


class LiveMultiTimeframeBuffer:
    """Own synchronized completed M5/M15/H1/H4 histories for live analysis."""

    _BASE_TIMEFRAMES = (
        Timeframe.M5,
        Timeframe.M15,
        Timeframe.H1,
        Timeframe.H4,
    )
    _DURATIONS = {
        Timeframe.M5: timedelta(minutes=5),
        Timeframe.M15: timedelta(minutes=15),
        Timeframe.H1: timedelta(hours=1),
        Timeframe.H4: timedelta(hours=4),
    }

    def __init__(self, window_bars: int = 500) -> None:
        if isinstance(window_bars, bool) or not isinstance(window_bars, int):
            raise TypeError("window_bars must be an integer")
        if window_bars < 2:
            raise ValueError("window_bars must be at least 2")

        self.window_bars = window_bars
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
        self._bars[timeframe] = validated[-self.window_bars :]

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
        if len(history) > self.window_bars:
            del history[: len(history) - self.window_bars]
        return True

    def snapshot(
        self,
        boundary: datetime,
    ) -> Mapping[Timeframe, tuple[MarketBar, ...]] | None:
        """Return the completed six-timeframe snapshot visible at boundary."""

        boundary = self._normalize_boundary(boundary)
        visible: dict[Timeframe, tuple[MarketBar, ...]] = {}

        for timeframe in self._BASE_TIMEFRAMES:
            duration = self._DURATIONS[timeframe]
            values = tuple(
                bar
                for bar in self._bars[timeframe]
                if bar.timestamp.astimezone(UTC) + duration <= boundary
            )
            if not values:
                return None
            visible[timeframe] = values[-self.window_bars :]

        h4_values = visible[Timeframe.H4]
        daily = tuple(
            self._aggregate_completed(
                h4_values,
                boundary=boundary,
                period=timedelta(days=1),
                weekly=False,
            )
        )
        weekly = tuple(
            self._aggregate_completed(
                h4_values,
                boundary=boundary,
                period=timedelta(days=7),
                weekly=True,
            )
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

    @classmethod
    def _aggregate_completed(
        cls,
        bars: Sequence[MarketBar],
        *,
        boundary: datetime,
        period: timedelta,
        weekly: bool,
    ) -> list[MarketBar]:
        buckets: dict[datetime, list[MarketBar]] = {}
        for bar in bars:
            timestamp = bar.timestamp.astimezone(UTC)
            day = datetime(
                timestamp.year,
                timestamp.month,
                timestamp.day,
                tzinfo=UTC,
            )
            start = (
                day - timedelta(days=timestamp.weekday())
                if weekly
                else day
            )
            buckets.setdefault(start, []).append(bar)

        aggregated: list[MarketBar] = []
        for start in sorted(buckets):
            if start + period > boundary:
                continue
            values = buckets[start]
            aggregated.append(
                MarketBar(
                    timestamp=start,
                    open=float(values[0].open),
                    high=max(float(item.high) for item in values),
                    low=min(float(item.low) for item in values),
                    close=float(values[-1].close),
                    tick_volume=sum(int(item.tick_volume) for item in values),
                )
            )
        return aggregated

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
        if not isinstance(boundary, datetime):
            raise TypeError("boundary must be a datetime")
        if boundary.tzinfo is None or boundary.utcoffset() is None:
            raise ValueError("boundary must be timezone-aware")
        return boundary.astimezone(UTC)
