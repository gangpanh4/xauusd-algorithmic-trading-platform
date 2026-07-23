from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.backtesting.config import BacktestConfig
from core.backtesting.engine import BacktestingEngine
from core.multi_timeframe.enums import Timeframe
from core.regime_detector.models import MarketBar
from core.trading_pipeline.market_context import MarketContext


BASE = datetime(2026, 1, 5, tzinfo=UTC)  # Monday


def bar(ts: datetime, price: float = 100.0) -> MarketBar:
    return MarketBar(
        timestamp=ts,
        open=price,
        high=price + 1.0,
        low=price - 1.0,
        close=price + 0.25,
        volume=10.0,
        tick_volume=10,
    )


class _FakeM5State:
    def __init__(self) -> None:
        self.market_structure = object()


class _FakeMtfResult:
    def __init__(self) -> None:
        self.m5 = _FakeM5State()


class FakeMtf:
    def __init__(self) -> None:
        self.calls = []
        self.result = _FakeMtfResult()

    def process(self, mapping):
        self.calls.append(mapping)
        return self.result


class FakeConfluence:
    def __init__(self) -> None:
        self.calls = []
        self.result = object()

    def evaluate_multi_timeframe(self, value):
        self.calls.append(value)
        return self.result


class FakePipeline:
    def __init__(self) -> None:
        self.multi_timeframe = FakeMtf()
        self.confluence_engine = FakeConfluence()
        self.process_calls = []
        self.result = object()

    def process_bar(self, value, **kwargs):
        self.process_calls.append((value, kwargs))
        return self.result


class LegacyPipeline:
    def __init__(self) -> None:
        self.calls = []
        self.result = object()

    def process_bar(self, value, **kwargs):
        self.calls.append((value, kwargs))
        return self.result


def context_for(boundary_open: datetime) -> MarketContext:
    # Eight days of H4 history are enough for one completed weekly aggregate.
    h4 = [bar(BASE + timedelta(hours=4 * i)) for i in range(48)]
    h1 = [bar(BASE + timedelta(hours=i)) for i in range(192)]
    m15 = [bar(BASE + timedelta(minutes=15 * i)) for i in range(768)]
    m5 = [bar(BASE + timedelta(minutes=5 * i)) for i in range(2304)]
    current = next(value for value in m15 if value.timestamp == boundary_open)
    return MarketContext(
        current_bar=current,
        m5_bars=m5,
        m15_bars=m15,
        h1_bars=h1,
        h4_bars=h4,
    )


def test_engine_builds_no_lookahead_six_timeframe_snapshot() -> None:
    observation = BASE + timedelta(days=7, hours=12)
    context = context_for(observation)
    engine = BacktestingEngine(
        BacktestConfig(),
        multi_timeframe_window_bars=50,
        progress_interval_bars=None,
    )
    pipeline = FakePipeline()
    engine.pipeline = pipeline

    result, signal_bar = engine._process_observation(
        context=context,
        m15_index=0,
        m15_bar=context.current_bar,
    )

    assert result is pipeline.result

    # Strategy replay now advances through every newly completed M5 snapshot.
    # The active M15 pipeline consumes the final snapshot at this boundary.
    mapping = pipeline.multi_timeframe.calls[-1]

    assert set(mapping) == set(Timeframe)
    assert all(len(values) <= 50 for values in mapping.values())

    boundary = observation + timedelta(minutes=15)
    assert mapping[Timeframe.M5][-1].timestamp + timedelta(minutes=5) <= boundary
    assert mapping[Timeframe.H1][-1].timestamp + timedelta(hours=1) <= boundary
    assert mapping[Timeframe.H4][-1].timestamp + timedelta(hours=4) <= boundary
    assert mapping[Timeframe.WEEKLY][-1].timestamp + timedelta(days=7) <= boundary
    assert mapping[Timeframe.DAILY][-1].timestamp + timedelta(days=1) <= boundary
    assert signal_bar.timestamp == mapping[Timeframe.M5][-1].timestamp

    kwargs = pipeline.process_calls[0][1]
    assert kwargs["confluence"] is pipeline.confluence_engine.result
    assert kwargs["multi_timeframe_result"] is pipeline.multi_timeframe.result
    assert (
        kwargs["market_structure_result"]
        is pipeline.multi_timeframe.result.m5.market_structure
    )


def test_unclosed_higher_timeframe_candles_are_not_visible() -> None:
    observation = BASE + timedelta(days=7, hours=10, minutes=45)
    context = context_for(observation)
    engine = BacktestingEngine(BacktestConfig(), progress_interval_bars=None)
    pipeline = FakePipeline()
    engine.pipeline = pipeline

    engine._process_observation(
        context=context,
        m15_index=0,
        m15_bar=context.current_bar,
    )

    # Inspect the final snapshot used at the current M15 boundary, not the
    # earliest replayed M5 snapshot.
    mapping = pipeline.multi_timeframe.calls[-1]
    boundary = observation + timedelta(minutes=15)

    assert all(
        value.timestamp + timedelta(hours=4) <= boundary
        for value in mapping[Timeframe.H4]
    )


def test_legacy_injected_pipeline_keeps_process_bar_contract() -> None:
    observation = BASE + timedelta(hours=1)
    context = context_for(observation)
    engine = BacktestingEngine(BacktestConfig(), progress_interval_bars=None)
    pipeline = LegacyPipeline()
    engine.pipeline = pipeline

    result, used_bar = engine._process_observation(
        context=context,
        m15_index=0,
        m15_bar=context.current_bar,
    )

    assert result is pipeline.result
    assert used_bar is context.current_bar
    assert pipeline.calls[0][0] is context.current_bar


@pytest.mark.parametrize("value", [True, 0, 1, 1.5, "500"])
def test_invalid_multi_timeframe_window_fails_closed(value) -> None:
    with pytest.raises((TypeError, ValueError)):
        BacktestingEngine(
            BacktestConfig(),
            multi_timeframe_window_bars=value,
        )
