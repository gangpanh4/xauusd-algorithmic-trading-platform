from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.data.models import MarketBar
from core.multi_timeframe.enums import Timeframe
from core.platform.engine import TradingPlatform

START = datetime(2026, 1, 5, tzinfo=UTC)


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


class _Service:
    def __init__(self, bars: list[MarketBar]) -> None:
        self.bars = bars
        self.calls: list[int] = []

    def get_historical_bars(self, count: int) -> list[MarketBar]:
        self.calls.append(count)
        return list(self.bars)


def _services() -> dict[Timeframe, _Service]:
    return {
        Timeframe.M5: _Service(_series(6_048, timedelta(minutes=5))),
        Timeframe.M15: _Service(_series(2_016, timedelta(minutes=15))),
        Timeframe.H1: _Service(_series(504, timedelta(hours=1))),
        Timeframe.H4: _Service(_series(126, timedelta(hours=4))),
    }


def test_live_bootstrap_uses_one_m5_boundary_and_aligned_counts() -> None:
    services = _services()
    latest = services[Timeframe.M5].bars[5_616]

    histories, capacities, source_start, boundary = (
        TradingPlatform._load_aligned_live_histories(
            services=services,  # type: ignore[arg-type]
            latest_m5=latest,
            analysis_window_bars=48,
        )
    )

    assert boundary == latest.timestamp + timedelta(minutes=5)
    assert source_start.weekday() == 0
    assert source_start.hour == 0
    assert len(set(capacities.values())) == 4
    assert histories[Timeframe.M5][-1] == latest
    for timeframe, values in histories.items():
        assert values
        assert values[0].timestamp >= source_start
        assert services[timeframe].calls


def test_live_bootstrap_fails_when_h4_overlap_is_insufficient() -> None:
    services = _services()
    services[Timeframe.H4].bars = services[Timeframe.H4].bars[-20:]
    latest = services[Timeframe.M5].bars[5_616]

    with pytest.raises(RuntimeError, match="Insufficient completed H4"):
        TradingPlatform._load_aligned_live_histories(
            services=services,  # type: ignore[arg-type]
            latest_m5=latest,
            analysis_window_bars=48,
        )
