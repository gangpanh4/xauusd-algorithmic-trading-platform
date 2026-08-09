from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.data.models import MarketBar
from core.live_trading.multi_timeframe_buffer import LiveMultiTimeframeBuffer
from core.multi_timeframe.enums import Timeframe

START = datetime(2026, 1, 5, tzinfo=UTC)
WINDOW = 48


def _bar(timestamp: datetime, price: float = 100.0) -> MarketBar:
    return MarketBar(
        timestamp=timestamp,
        open=price,
        high=price + 1.0,
        low=price - 1.0,
        close=price + 0.25,
        tick_volume=100,
    )


def _series(count: int, step: timedelta) -> list[MarketBar]:
    return [_bar(START + step * index, 100.0 + index) for index in range(count)]


def _histories() -> dict[Timeframe, list[MarketBar]]:
    return {
        Timeframe.M5: _series(4_608, timedelta(minutes=5)),
        Timeframe.M15: _series(1_536, timedelta(minutes=15)),
        Timeframe.H1: _series(384, timedelta(hours=1)),
        Timeframe.H4: _series(96, timedelta(hours=4)),
    }


def _buffer() -> LiveMultiTimeframeBuffer:
    histories = _histories()
    buffer = LiveMultiTimeframeBuffer(
        window_bars=WINDOW,
        source_capacity_bars={
            timeframe: len(values)
            for timeframe, values in histories.items()
        },
    )
    for timeframe, values in histories.items():
        buffer.load(timeframe, values)
    return buffer


def test_snapshot_exposes_exact_completed_rolling_windows() -> None:
    buffer = _buffer()
    boundary = START + timedelta(days=14, hours=12, minutes=5)

    snapshot = buffer.snapshot(boundary)

    assert snapshot is not None
    for timeframe in (Timeframe.M5, Timeframe.M15, Timeframe.H1, Timeframe.H4):
        assert len(snapshot[timeframe]) == WINDOW
    assert snapshot[Timeframe.M5][-1].timestamp == boundary - timedelta(minutes=5)
    assert all(
        bar.timestamp + timedelta(hours=1) <= boundary
        for bar in snapshot[Timeframe.H1]
    )
    assert all(
        bar.timestamp + timedelta(hours=4) <= boundary
        for bar in snapshot[Timeframe.H4]
    )
    assert snapshot[Timeframe.DAILY]
    assert snapshot[Timeframe.WEEKLY]


def test_incomplete_leading_history_returns_no_snapshot() -> None:
    histories = _histories()
    buffer = LiveMultiTimeframeBuffer(window_bars=WINDOW)
    for timeframe, values in histories.items():
        buffer.load(timeframe, values[: WINDOW - 1])

    assert buffer.snapshot(START + timedelta(days=16)) is None


def test_duplicate_m5_does_not_create_a_second_decision_boundary() -> None:
    buffer = _buffer()
    latest = buffer.histories[Timeframe.M5][-1]

    assert buffer.append(Timeframe.M5, latest) is False

    revised = MarketBar(
        timestamp=latest.timestamp,
        open=latest.open,
        high=latest.high + 1.0,
        low=latest.low,
        close=latest.close,
        tick_volume=latest.tick_volume,
    )
    with pytest.raises(ValueError, match="Revised completed M5"):
        buffer.append(Timeframe.M5, revised)


def test_source_capacity_retains_warmup_beyond_exposed_window() -> None:
    buffer = _buffer()

    assert len(buffer.histories[Timeframe.M5]) > WINDOW
    snapshot = buffer.snapshot(START + timedelta(days=14, hours=12, minutes=5))
    assert snapshot is not None
    assert len(snapshot[Timeframe.M5]) == WINDOW
