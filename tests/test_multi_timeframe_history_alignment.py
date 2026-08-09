from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.data.models import MarketBar
from core.multi_timeframe.enums import Timeframe
from core.multi_timeframe.history_alignment import (
    bar_close_time,
    clip_history,
    completed_period_buckets,
    required_bar_count,
    visible_bars,
)


def _bar(timestamp: datetime, price: float = 100.0) -> MarketBar:
    return MarketBar(
        timestamp=timestamp,
        open=price,
        high=price + 1.0,
        low=price - 1.0,
        close=price + 0.25,
        tick_volume=100,
    )


def test_close_time_and_visibility_use_completed_bar_semantics() -> None:
    start = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
    bars = (_bar(start), _bar(start + timedelta(minutes=5)))

    assert bar_close_time(bars[0], Timeframe.M5) == start + timedelta(minutes=5)
    assert visible_bars(
        bars,
        timeframe=Timeframe.M5,
        boundary=start + timedelta(minutes=9),
    ) == (bars[0],)


def test_clipping_preserves_provider_gaps_without_fabricating_bars() -> None:
    start = datetime(2026, 1, 5, tzinfo=UTC)
    bars = (
        _bar(start),
        _bar(start + timedelta(minutes=5)),
        _bar(start + timedelta(minutes=15)),
    )

    clipped = clip_history(
        bars,
        timeframe=Timeframe.M5,
        start=start,
        end=start + timedelta(minutes=20),
    )

    assert clipped == bars
    assert start + timedelta(minutes=10) not in {
        bar.timestamp for bar in clipped
    }


def test_required_counts_are_calculated_from_one_wall_clock_span() -> None:
    start = datetime(2026, 1, 5, tzinfo=UTC)
    end = start + timedelta(days=7)

    assert required_bar_count(
        start=start,
        end=end,
        timeframe=Timeframe.M5,
    ) == 2_018
    assert required_bar_count(
        start=start,
        end=end,
        timeframe=Timeframe.H4,
    ) == 44


def test_derived_buckets_exclude_only_the_truncated_leading_bucket() -> None:
    monday = datetime(2026, 1, 5, tzinfo=UTC)
    bars = tuple(
        _bar(monday + timedelta(hours=4 * index))
        for index in range(3, 48)
    )
    boundary = monday + timedelta(days=8)

    daily = completed_period_buckets(
        bars,
        boundary=boundary,
        weekly=False,
    )
    weekly = completed_period_buckets(
        bars,
        boundary=boundary,
        weekly=True,
    )

    assert daily[0][0] == monday + timedelta(days=1)
    assert weekly == ()

    extended = bars + tuple(
        _bar(monday + timedelta(hours=4 * index))
        for index in range(48, 90)
    )
    weekly = completed_period_buckets(
        extended,
        boundary=monday + timedelta(days=15),
        weekly=True,
    )
    assert weekly[0][0] == monday + timedelta(days=7)
