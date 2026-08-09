from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from core.backtesting.config import BacktestConfig
from core.backtesting.engine import BacktestingEngine
from core.backtesting.models import BacktestReplayContext, BacktestReplayWindow
from core.data.models import MarketBar as LiveBar
from core.live_trading.multi_timeframe_buffer import LiveMultiTimeframeBuffer
from core.multi_timeframe.enums import Timeframe
from core.regime_detector.models import MarketBar

START = datetime(2026, 1, 5, tzinfo=UTC)
WINDOW = 48


def _backtest_bar(timestamp: datetime, price: float) -> MarketBar:
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
    return [
        _backtest_bar(START + step * index, 100.0 + index)
        for index in range(count)
    ]


def _context() -> BacktestReplayContext:
    m5 = _series(4_608, timedelta(minutes=5))
    m15 = _series(1_536, timedelta(minutes=15))
    h1 = _series(384, timedelta(hours=1))
    h4 = _series(96, timedelta(hours=4))
    eligible_start = START + timedelta(days=14, minutes=10)
    return BacktestReplayContext(
        current_bar=m5[-1],
        m5_bars=m5,
        m15_bars=m15,
        h1_bars=h1,
        h4_bars=h4,
        replay_window=BacktestReplayWindow(
            source_start=START,
            source_end=START + timedelta(days=16),
            first_eligible_m5_timestamp=eligible_start,
            last_eligible_m5_timestamp=m5[-1].timestamp,
            requested_eligible_m5_bars=sum(
                bar.timestamp >= eligible_start for bar in m5
            ),
            analysis_window_bars=WINDOW,
            required_warmup_snapshots=2,
            available_warmup_snapshots=2,
            requested_bar_counts=(),
        ),
    )


class _Mtf:
    def __init__(self) -> None:
        self.calls: list[object] = []
        self.result = SimpleNamespace(
            m5=SimpleNamespace(market_structure=object())
        )

    def process(self, snapshot):
        self.calls.append(snapshot)
        return self.result


class _Confluence:
    def evaluate_multi_timeframe(self, result):
        return result


class _Pipeline:
    def __init__(self) -> None:
        self.multi_timeframe = _Mtf()
        self.confluence_engine = _Confluence()
        self.process_calls: list[tuple[MarketBar, dict[str, object]]] = []

    def synchronize_account_balance(self, balance, *, timestamp=None) -> None:
        del balance, timestamp

    def process_bar(self, bar: MarketBar, **kwargs: object):
        self.process_calls.append((bar, kwargs))
        return SimpleNamespace(
            trade_plan=None,
            signal=None,
            trade_quality=None,
            features=None,
            regime=None,
        )


def _live_bar(bar: MarketBar) -> LiveBar:
    return LiveBar(
        timestamp=bar.timestamp,
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        tick_volume=int(bar.tick_volume or 0),
    )


def _canonical(snapshot) -> dict[Timeframe, tuple[tuple[object, ...], ...]]:
    return {
        timeframe: tuple(
            (
                bar.timestamp,
                float(bar.open),
                float(bar.high),
                float(bar.low),
                float(bar.close),
                int(bar.tick_volume),
            )
            for bar in values
        )
        for timeframe, values in snapshot.items()
    }


def test_backtest_and_live_build_identical_m5_snapshot_sequence() -> None:
    context = _context()
    pipeline = _Pipeline()
    engine = BacktestingEngine(
        BacktestConfig(warmup_bars=2),
        multi_timeframe_window_bars=WINDOW,
        progress_interval_bars=None,
    )
    engine._create_pipeline = lambda: pipeline  # type: ignore[method-assign]
    engine.run(context)

    capacities = {
        Timeframe.M5: len(context.m5_bars),
        Timeframe.M15: len(context.m15_bars),
        Timeframe.H1: len(context.h1_bars),
        Timeframe.H4: len(context.h4_bars),
    }
    buffer = LiveMultiTimeframeBuffer(
        window_bars=WINDOW,
        source_capacity_bars=capacities,
    )
    sources = {
        Timeframe.M5: context.m5_bars,
        Timeframe.M15: context.m15_bars,
        Timeframe.H1: context.h1_bars,
        Timeframe.H4: context.h4_bars,
    }
    for timeframe, values in sources.items():
        buffer.load(timeframe, [_live_bar(bar) for bar in values])

    live_snapshots = []
    for m5_bar in context.m5_bars:
        snapshot = buffer.snapshot(m5_bar.timestamp + timedelta(minutes=5))
        if snapshot is not None:
            live_snapshots.append(snapshot)

    backtest_timestamps = [bar.timestamp for bar, _ in pipeline.process_calls]
    live_timestamps = [
        snapshot[Timeframe.M5][-1].timestamp
        for snapshot in live_snapshots
    ]
    assert backtest_timestamps == live_timestamps
    assert len(backtest_timestamps) == len(set(backtest_timestamps))
    assert all(bar in context.m5_bars for bar, _ in pipeline.process_calls)
    assert [
        _canonical(snapshot) for snapshot in pipeline.multi_timeframe.calls
    ] == [_canonical(snapshot) for snapshot in live_snapshots]

    first_eligible = context.replay_window.first_eligible_m5_timestamp
    assert first_eligible in backtest_timestamps
    assert sum(timestamp < first_eligible for timestamp in backtest_timestamps) >= 2


def test_forming_higher_timeframes_are_invisible_in_both_paths() -> None:
    context = _context()
    engine = BacktestingEngine(
        BacktestConfig(),
        multi_timeframe_window_bars=WINDOW,
        progress_interval_bars=None,
    )
    engine._prepare_mtf_runtime_cache(context)
    m5_bar = next(
        bar
        for bar in context.m5_bars
        if bar.timestamp == START + timedelta(days=14, hours=10, minutes=45)
    )
    boundary = m5_bar.timestamp + timedelta(minutes=5)
    snapshot = engine._strategy_mtf_snapshot(
        boundary=boundary,
        m5_end=context.m5_bars.index(m5_bar) + 1,
    )

    assert snapshot is not None
    assert snapshot[Timeframe.H1][-1].timestamp + timedelta(hours=1) <= boundary
    assert snapshot[Timeframe.H4][-1].timestamp + timedelta(hours=4) <= boundary


def test_duplicate_or_insufficient_m5_history_fails_deterministically() -> None:
    context = _context()
    context.m5_bars[2] = context.m5_bars[1]
    engine = BacktestingEngine(
        BacktestConfig(),
        multi_timeframe_window_bars=WINDOW,
        progress_interval_bars=None,
    )

    with pytest.raises(ValueError, match="strictly increasing"):
        engine.run(context)

    short = _context()
    short.h4_bars = short.h4_bars[: WINDOW - 1]
    pipeline = _Pipeline()
    engine._create_pipeline = lambda: pipeline  # type: ignore[method-assign]
    engine.run(short)
    assert pipeline.process_calls == []
