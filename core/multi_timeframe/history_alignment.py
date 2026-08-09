"""Pure completed-bar history alignment primitives."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Protocol, TypeVar

from .enums import Timeframe


class TimestampedBar(Protocol):
    """Structural type required by the temporal alignment helpers."""

    timestamp: datetime


BarT = TypeVar("BarT", bound=TimestampedBar)


BASE_TIMEFRAME_DURATIONS: Mapping[Timeframe, timedelta] = {
    Timeframe.M5: timedelta(minutes=5),
    Timeframe.M15: timedelta(minutes=15),
    Timeframe.H1: timedelta(hours=1),
    Timeframe.H4: timedelta(hours=4),
}


def normalize_utc(value: datetime, field_name: str) -> datetime:
    """Return an aware datetime normalized to UTC."""

    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def timeframe_duration(timeframe: Timeframe) -> timedelta:
    """Return the duration of one supported source candle."""

    if not isinstance(timeframe, Timeframe):
        raise TypeError("timeframe must be a Timeframe")
    try:
        return BASE_TIMEFRAME_DURATIONS[timeframe]
    except KeyError as exc:
        raise ValueError(
            "Only M5, M15, H1, and H4 have source-candle durations."
        ) from exc


def bar_close_time(bar: TimestampedBar, timeframe: Timeframe) -> datetime:
    """Return the UTC close boundary for one open-timestamped candle."""

    return normalize_utc(bar.timestamp, "bar timestamp") + timeframe_duration(
        timeframe
    )


def completed_by_boundary(
    bar: TimestampedBar,
    timeframe: Timeframe,
    boundary: datetime,
) -> bool:
    """Return whether a candle is completed by an inclusive boundary."""

    return bar_close_time(bar, timeframe) <= normalize_utc(
        boundary,
        "boundary",
    )


def clip_history(
    bars: Sequence[BarT],
    *,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
) -> tuple[BarT, ...]:
    """Clip source bars to a common open/start and completed/end window."""

    start_utc = normalize_utc(start, "start")
    end_utc = normalize_utc(end, "end")
    if start_utc >= end_utc:
        raise ValueError("start must be before end")

    return tuple(
        bar
        for bar in bars
        if normalize_utc(bar.timestamp, "bar timestamp") >= start_utc
        and completed_by_boundary(bar, timeframe, end_utc)
    )


def visible_bars(
    bars: Sequence[BarT],
    *,
    timeframe: Timeframe,
    boundary: datetime,
    window_bars: int | None = None,
) -> tuple[BarT, ...]:
    """Return completed bars visible at one boundary, optionally windowed."""

    boundary_utc = normalize_utc(boundary, "boundary")
    visible = tuple(
        bar
        for bar in bars
        if completed_by_boundary(bar, timeframe, boundary_utc)
    )
    if window_bars is None:
        return visible
    if isinstance(window_bars, bool) or not isinstance(window_bars, int):
        raise TypeError("window_bars must be an integer or None")
    if window_bars < 1:
        raise ValueError("window_bars must be at least 1")
    return visible[-window_bars:]


def required_bar_count(
    *,
    start: datetime,
    end: datetime,
    timeframe: Timeframe,
) -> int:
    """Calculate a deterministic count that covers one wall-clock span.

    The two-bar margin covers an inclusive edge and a potentially returned
    forming candle. Weekends and provider gaps are deliberately not removed
    from the span; requesting those slots cannot fabricate missing candles.
    """

    start_utc = normalize_utc(start, "start")
    end_utc = normalize_utc(end, "end")
    if start_utc >= end_utc:
        raise ValueError("start must be before end")
    duration = timeframe_duration(timeframe)
    return ceil((end_utc - start_utc) / duration) + 2


def utc_day_start(value: datetime) -> datetime:
    """Return the UTC midnight containing ``value``."""

    normalized = normalize_utc(value, "value")
    return datetime(
        normalized.year,
        normalized.month,
        normalized.day,
        tzinfo=UTC,
    )


def utc_week_start(value: datetime) -> datetime:
    """Return the UTC Monday midnight containing ``value``."""

    day = utc_day_start(value)
    return day - timedelta(days=day.weekday())


def completed_period_buckets(
    bars: Sequence[BarT],
    *,
    boundary: datetime,
    weekly: bool,
) -> tuple[tuple[datetime, tuple[BarT, ...]], ...]:
    """Group source bars into completed UTC day or week buckets.

    A leading bucket is excluded when the supplied history begins after that
    bucket's UTC boundary. This prevents a clipped rolling H4 window from
    presenting a partial day or week as a complete derived candle. Later
    provider gaps remain untouched and no source bars are synthesized.
    """

    boundary_utc = normalize_utc(boundary, "boundary")
    if not bars:
        return ()

    buckets: dict[datetime, list[BarT]] = {}
    previous: datetime | None = None
    for bar in bars:
        timestamp = normalize_utc(bar.timestamp, "bar timestamp")
        if previous is not None and timestamp <= previous:
            raise ValueError("bar timestamps must be strictly increasing")
        previous = timestamp
        start = utc_week_start(timestamp) if weekly else utc_day_start(timestamp)
        buckets.setdefault(start, []).append(bar)

    first_timestamp = normalize_utc(bars[0].timestamp, "bar timestamp")
    period = timedelta(days=7 if weekly else 1)
    completed: list[tuple[datetime, tuple[BarT, ...]]] = []
    for index, start in enumerate(sorted(buckets)):
        if index == 0 and first_timestamp != start:
            continue
        if start + period > boundary_utc:
            continue
        completed.append((start, tuple(buckets[start])))
    return tuple(completed)
