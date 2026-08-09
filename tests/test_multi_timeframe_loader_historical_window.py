from __future__ import annotations

from datetime import UTC, datetime, timedelta

import MetaTrader5 as mt5
import pytest

from core.backtesting.multi_timeframe_loader import MultiTimeframeLoader
from core.regime_detector.models import MarketBar

START = datetime(2026, 1, 5, tzinfo=UTC)  # Monday


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


def _series(count: int, step: timedelta) -> list[MarketBar]:
    return [_bar(START + index * step, 3000.0 + index) for index in range(count)]


def _histories() -> dict[str, list[MarketBar]]:
    return {
        "m5": _series(5_760, timedelta(minutes=5)),
        "m15": _series(1_920, timedelta(minutes=15)),
        "h1": _series(480, timedelta(hours=1)),
        "h4": _series(120, timedelta(hours=4)),
    }


class _WindowHistoryLoader:
    def __init__(self) -> None:
        self.histories = _histories()
        self.calls: list[tuple[str, int, int, datetime]] = []

    def load_history(
        self,
        symbol: str,
        timeframe: int,
        bars: int,
        *,
        end_time: datetime,
    ) -> list[MarketBar]:
        mapping = {
            mt5.TIMEFRAME_M5: "m5",
            mt5.TIMEFRAME_M15: "m15",
            mt5.TIMEFRAME_H1: "h1",
            mt5.TIMEFRAME_H4: "h4",
        }
        self.calls.append((symbol, timeframe, bars, end_time))
        return list(self.histories[mapping[timeframe]])


def test_explicit_window_calculates_aligned_per_timeframe_counts() -> None:
    fake = _WindowHistoryLoader()
    now = START + timedelta(days=21)
    boundary = START + timedelta(days=19, hours=12, minutes=7)
    loader = MultiTimeframeLoader(loader=fake, clock=lambda: now)

    context = loader.load(
        "XAUUSD",
        20,
        end_time=boundary,
        warmup_bars=5,
        analysis_window_bars=96,
    )

    final_calls = fake.calls[-4:]
    assert {call[3] for call in final_calls} == {boundary}
    assert len({call[2] for call in final_calls}) == 4
    assert {call[0] for call in fake.calls} == {"XAUUSD"}
    assert context.replay_window.requested_eligible_m5_bars == 20
    assert context.replay_window.analysis_window_bars == 96
    assert context.replay_window.available_warmup_snapshots >= 5
    assert len(context.m5_bars) > 20
    assert context.current_bar.timestamp == START + timedelta(
        days=19,
        hours=12,
    )
    assert all(
        bar.timestamp + timedelta(minutes=5) <= boundary
        for bar in context.m5_bars
    )


def test_future_window_is_rejected_before_history_loading() -> None:
    fake = _WindowHistoryLoader()
    now = START + timedelta(days=21)
    loader = MultiTimeframeLoader(loader=fake, clock=lambda: now)

    with pytest.raises(ValueError, match="future"):
        loader.load(
            "XAUUSD",
            20,
            end_time=now + timedelta(minutes=1),
            warmup_bars=5,
            analysis_window_bars=96,
        )

    assert fake.calls == []


def test_naive_window_is_rejected() -> None:
    loader = MultiTimeframeLoader(
        loader=_WindowHistoryLoader(),
        clock=lambda: START + timedelta(days=21),
    )

    with pytest.raises(ValueError, match="end_time must be timezone-aware"):
        loader.load(
            "XAUUSD",
            20,
            end_time=datetime(2026, 1, 20, tzinfo=UTC).replace(tzinfo=None),
            warmup_bars=5,
            analysis_window_bars=96,
        )


def test_latest_load_captures_one_clock_boundary_for_final_histories() -> None:
    fake = _WindowHistoryLoader()
    now = START + timedelta(days=19, hours=12, minutes=7)
    loader = MultiTimeframeLoader(loader=fake, clock=lambda: now)

    context = loader.load(
        "XAUUSD",
        20,
        warmup_bars=5,
        analysis_window_bars=96,
    )

    assert {call[3] for call in fake.calls[-4:]} == {now}
    assert context.replay_window.source_end == now


def test_insufficient_overlap_fails_closed_without_filling_gaps() -> None:
    fake = _WindowHistoryLoader()
    fake.histories["h4"] = fake.histories["h4"][-20:]
    loader = MultiTimeframeLoader(
        loader=fake,
        clock=lambda: START + timedelta(days=21),
    )

    with pytest.raises(RuntimeError, match="Insufficient H4"):
        loader.load(
            "XAUUSD",
            20,
            end_time=START + timedelta(days=19, hours=12),
            warmup_bars=5,
            analysis_window_bars=96,
        )
