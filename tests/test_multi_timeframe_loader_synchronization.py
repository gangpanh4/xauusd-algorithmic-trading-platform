from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from core.backtesting.multi_timeframe_loader import MultiTimeframeLoader
from core.regime_detector.models import MarketBar


def _bar(timestamp: datetime, price: float = 2000.0) -> MarketBar:
    return MarketBar(
        timestamp=timestamp,
        open=price,
        high=price + 1.0,
        low=price - 1.0,
        close=price + 0.25,
        volume=100.0,
        tick_volume=100,
    )


def _series(start: datetime, count: int, step: timedelta) -> list[MarketBar]:
    return [_bar(start + step * index, 2000.0 + index) for index in range(count)]


def _histories() -> dict[str, list[MarketBar]]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    return {
        "m5": _series(base, 133, timedelta(minutes=5)),
        "m15": _series(base, 45, timedelta(minutes=15)),
        "h1": _series(base, 12, timedelta(hours=1)),
        "h4": _series(base, 4, timedelta(hours=4)),
    }


class _FakeHistoryLoader:
    def __init__(self, histories: dict[str, list[MarketBar]]) -> None:
        self.histories = histories
        self.calls: list[tuple[str, int, int, datetime | None]] = []

    def load_history(
        self,
        symbol: str,
        timeframe: int,
        bars: int,
        *,
        end_time: datetime | None = None,
    ) -> list[MarketBar]:
        import MetaTrader5 as mt5

        mapping = {
            mt5.TIMEFRAME_M5: "m5",
            mt5.TIMEFRAME_M15: "m15",
            mt5.TIMEFRAME_H1: "h1",
            mt5.TIMEFRAME_H4: "h4",
        }
        self.calls.append((symbol, timeframe, bars, end_time))
        return list(self.histories[mapping[timeframe]])


def test_synchronize_at_excludes_unclosed_higher_timeframe_bars() -> None:
    histories = _histories()
    loader = MultiTimeframeLoader(loader=_FakeHistoryLoader(histories))
    observation = datetime(2026, 1, 1, 10, 45, tzinfo=UTC)

    context = loader.synchronize_at(
        histories=histories,
        observation_timestamp=observation,
    )

    assert context.current_bar.timestamp == observation
    assert context.m5_bars[-1].timestamp == observation
    assert context.m15_bars[-1].timestamp == datetime(
        2026, 1, 1, 10, 30, tzinfo=UTC
    )
    assert context.h1_bars[-1].timestamp == datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
    assert context.h4_bars[-1].timestamp == datetime(2026, 1, 1, 4, 0, tzinfo=UTC)
    assert all(bar.timestamp < datetime(2026, 1, 1, 8, 0, tzinfo=UTC) for bar in context.h4_bars)


def test_synchronization_excludes_still_forming_source_candles() -> None:
    histories = _histories()
    loader = MultiTimeframeLoader(loader=_FakeHistoryLoader(histories))

    context = loader.synchronize_at(
        histories=histories,
        observation_timestamp=datetime(2026, 1, 1, 11, 0, tzinfo=UTC),
    )

    assert context.current_bar.timestamp == datetime(2026, 1, 1, 11, 0, tzinfo=UTC)
    assert context.m15_bars[-1].timestamp == datetime(
        2026, 1, 1, 10, 45, tzinfo=UTC
    )
    assert context.h1_bars[-1].timestamp == datetime(2026, 1, 1, 10, 0, tzinfo=UTC)


def test_non_utc_observation_is_normalized_before_matching() -> None:
    histories = _histories()
    loader = MultiTimeframeLoader(loader=_FakeHistoryLoader(histories))
    plus_seven = timezone(timedelta(hours=7))

    context = loader.synchronize_at(
        histories=histories,
            observation_timestamp=datetime(2026, 1, 1, 17, 45, tzinfo=plus_seven),
    )

    assert context.current_bar.timestamp == datetime(2026, 1, 1, 10, 45, tzinfo=UTC)


def test_iter_synchronized_yields_only_warmup_complete_snapshots() -> None:
    histories = _histories()
    loader = MultiTimeframeLoader(loader=_FakeHistoryLoader(histories))

    snapshots = list(
        loader.iter_synchronized(
            histories=histories,
            start_timestamp=datetime(2026, 1, 1, 7, 0, tzinfo=UTC),
            end_timestamp=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
        )
    )

    assert snapshots
    assert [snapshot.current_bar.timestamp for snapshot in snapshots] == sorted(
        snapshot.current_bar.timestamp for snapshot in snapshots
    )
    for snapshot in snapshots:
        boundary = snapshot.current_bar.timestamp + timedelta(minutes=5)
        assert snapshot.h1_bars[-1].timestamp + timedelta(hours=1) <= boundary
        assert snapshot.h4_bars[-1].timestamp + timedelta(hours=4) <= boundary


def test_observation_must_match_existing_m5_open() -> None:
    loader = MultiTimeframeLoader(loader=_FakeHistoryLoader(_histories()))

    with pytest.raises(ValueError, match="existing M5"):
        loader.synchronize_at(
            histories=_histories(),
            observation_timestamp=datetime(2026, 1, 1, 10, 47, tzinfo=UTC),
        )


def test_invalid_history_order_fails_closed() -> None:
    histories = _histories()
    histories["h1"][1], histories["h1"][2] = histories["h1"][2], histories["h1"][1]
    loader = MultiTimeframeLoader(loader=_FakeHistoryLoader(histories))

    with pytest.raises(ValueError, match="strictly increasing"):
        loader.synchronize_at(
            histories=histories,
            observation_timestamp=datetime(2026, 1, 1, 10, 45, tzinfo=UTC),
        )


def test_naive_clock_and_observation_fail_closed() -> None:
    with pytest.raises(ValueError, match="clock must be timezone-aware"):
        MultiTimeframeLoader(
            loader=_FakeHistoryLoader(_histories()),
            clock=lambda: datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None),
        )

    loader = MultiTimeframeLoader(loader=_FakeHistoryLoader(_histories()))
    with pytest.raises(ValueError, match="observation_timestamp"):
        loader.synchronize_at(
            histories=_histories(),
            observation_timestamp=datetime(
                2026,
                1,
                1,
                10,
                45,
                tzinfo=UTC,
            ).replace(tzinfo=None),
        )


def test_symbol_and_bar_count_validation() -> None:
    loader = MultiTimeframeLoader(loader=_FakeHistoryLoader(_histories()))

    with pytest.raises(ValueError, match="symbol"):
        loader.load("   ", 100)
    with pytest.raises(ValueError, match="at least 2"):
        loader.load("XAUUSD", 1)
