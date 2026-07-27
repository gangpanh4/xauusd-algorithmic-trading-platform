from __future__ import annotations

from datetime import UTC, datetime, timedelta

import MetaTrader5 as mt5
import pytest

from core.backtesting.multi_timeframe_loader import MultiTimeframeLoader
from core.regime_detector.models import MarketBar


def _bar(timestamp: datetime, price: float = 3000.0) -> MarketBar:
    return MarketBar(
        timestamp=timestamp,
        open=price,
        high=price + 1.0,
        low=price - 1.0,
        close=price + 0.25,
        volume=100.0,
        tick_volume=100,
    )


def _series(
    start: datetime,
    count: int,
    step: timedelta,
) -> list[MarketBar]:
    return [_bar(start + index * step, 3000.0 + index) for index in range(count)]


def _histories() -> dict[str, list[MarketBar]]:
    start = datetime(2026, 4, 8, 0, 0, tzinfo=UTC)
    return {
        "m5": _series(start, 600, timedelta(minutes=5)),
        "m15": _series(start, 200, timedelta(minutes=15)),
        "h1": _series(start, 50, timedelta(hours=1)),
        "h4": _series(start, 14, timedelta(hours=4)),
    }


class _WindowHistoryLoader:
    def __init__(self) -> None:
        self.histories = _histories()
        self.calls: list[tuple[str, int, int, datetime | None]] = []

    def load_history(
        self,
        symbol: str,
        timeframe: int,
        bars: int,
        *,
        end_time: datetime | None = None,
    ) -> list[MarketBar]:
        mapping = {
            mt5.TIMEFRAME_M5: "m5",
            mt5.TIMEFRAME_M15: "m15",
            mt5.TIMEFRAME_H1: "h1",
            mt5.TIMEFRAME_H4: "h4",
        }
        self.calls.append((symbol, timeframe, bars, end_time))
        return list(self.histories[mapping[timeframe]])


def test_explicit_window_uses_one_boundary_for_all_timeframes() -> None:
    fake = _WindowHistoryLoader()
    now = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)
    boundary = datetime(2026, 4, 9, 12, 7, tzinfo=UTC)
    loader = MultiTimeframeLoader(loader=fake, clock=lambda: now)

    context = loader.load(
        "XAUUSD",
        500,
        end_time=boundary,
    )

    assert len(fake.calls) == 4
    assert {call[3] for call in fake.calls} == {boundary}
    durations = {
        "m5_bars": timedelta(minutes=5),
        "m15_bars": timedelta(minutes=15),
        "h1_bars": timedelta(hours=1),
        "h4_bars": timedelta(hours=4),
    }
    for field, duration in durations.items():
        values = getattr(context, field)
        assert values
        assert all(bar.timestamp + duration <= boundary for bar in values)
    assert context.current_bar.timestamp == datetime(
        2026, 4, 9, 11, 45, tzinfo=UTC
    )


def test_future_window_is_rejected_before_history_loading() -> None:
    fake = _WindowHistoryLoader()
    now = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)
    loader = MultiTimeframeLoader(loader=fake, clock=lambda: now)

    with pytest.raises(ValueError, match="future"):
        loader.load(
            "XAUUSD",
            500,
            end_time=now + timedelta(minutes=1),
        )

    assert fake.calls == []


def test_naive_window_is_rejected() -> None:
    loader = MultiTimeframeLoader(
        loader=_WindowHistoryLoader(),
        clock=lambda: datetime(2026, 4, 10, 12, 0, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="end_time must be timezone-aware"):
        loader.load(
            "XAUUSD",
            500,
            end_time=datetime(2026, 4, 9, 12, 0),
        )


def test_latest_load_keeps_legacy_history_loader_signature() -> None:
    class LegacyLoader:
        def __init__(self) -> None:
            self.calls = 0
            self.histories = _histories()

        def load_history(
            self,
            symbol: str,
            timeframe: int,
            bars: int,
        ) -> list[MarketBar]:
            self.calls += 1
            mapping = {
                mt5.TIMEFRAME_M5: "m5",
                mt5.TIMEFRAME_M15: "m15",
                mt5.TIMEFRAME_H1: "h1",
                mt5.TIMEFRAME_H4: "h4",
            }
            return list(self.histories[mapping[timeframe]])

    fake = LegacyLoader()
    loader = MultiTimeframeLoader(
        loader=fake,
        clock=lambda: datetime(2026, 4, 10, 12, 0, tzinfo=UTC),
    )

    context = loader.load("XAUUSD", 500)

    assert context.m15_bars
    assert fake.calls == 4
