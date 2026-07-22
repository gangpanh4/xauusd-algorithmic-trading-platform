from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from core.backtesting.config import BacktestConfig
from core.backtesting.engine import BacktestingEngine
from core.backtesting.models import ExitReason
from core.backtesting.simulator import TradeSimulator
from core.feature_engineering.models import FeatureVector
from core.regime_detector.models import MarketBar
from core.risk_manager.models import RiskDecision, TradePlan
from core.signal_generator.models import SignalDirection, TradingSignal
from core.trading_pipeline.market_context import MarketContext


BASE_TIME = datetime(2025, 1, 1, tzinfo=UTC)


def make_bar(
    index: int,
    *,
    open_price: float = 100.0,
    high: float = 101.0,
    low: float = 99.0,
    close: float = 100.0,
) -> MarketBar:
    return MarketBar(
        timestamp=BASE_TIME + timedelta(minutes=15 * index),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=100.0,
        tick_volume=100,
    )


def make_context(bars: list[MarketBar]) -> MarketContext:
    return MarketContext(
        current_bar=bars[-1],
        m5_bars=bars,
        m15_bars=bars,
        h1_bars=bars,
        h4_bars=bars,
    )


class IncrementalPipeline:
    def __init__(self, *, approve_first: bool = True) -> None:
        self.approve_first = approve_first
        self.process_calls: list[dict[str, object]] = []
        self.opened = 0
        self.closed = 0
        self.completed: list[tuple[float, datetime | None, float | None]] = []

    def synchronize_account_balance(
        self,
        balance: float,
        *,
        timestamp: datetime | None = None,
    ) -> None:
        del balance, timestamp

    def process_bar(self, bar: MarketBar, **kwargs: object) -> SimpleNamespace:
        self.process_calls.append({"bar": bar, **kwargs})
        approved = self.approve_first and len(self.process_calls) == 1
        signal = TradingSignal(
            timestamp=bar.timestamp,
            direction=SignalDirection.BUY if approved else SignalDirection.HOLD,
        )
        plan = TradePlan(
            timestamp=bar.timestamp,
            signal=signal,
            decision=RiskDecision.APPROVE if approved else RiskDecision.SKIP,
            position_size=0.10 if approved else 0.0,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            risk_reward_ratio=2.0,
            probability=0.70,
            confidence=0.80,
            feature_count=0,
            evidence_count=0,
            regime="TEST",
        )
        return SimpleNamespace(
            signal=signal,
            trade_plan=plan,
            trade_quality=None,
            features=FeatureVector(),
        )

    def register_position_opened(self, count: int = 1) -> None:
        self.opened += count

    def register_position_closed(self, count: int = 1) -> None:
        self.closed += count

    def register_completed_trade(
        self,
        pnl: float,
        *,
        timestamp: datetime | None = None,
        balance_after: float | None = None,
    ) -> None:
        self.completed.append((pnl, timestamp, balance_after))


class NoBatchSimulator(TradeSimulator):
    def simulate(self, *_: object, **__: object):  # type: ignore[no-untyped-def]
        raise AssertionError("production engine must not call batch simulate()")


def make_engine(
    bars: list[MarketBar],
    *,
    maximum_trades: int | None = 1,
    progress_interval_bars: int | None = None,
    approve_first: bool = True,
) -> tuple[BacktestingEngine, IncrementalPipeline]:
    engine = BacktestingEngine(
        BacktestConfig(warmup_bars=0, maximum_trades=maximum_trades),
        tick_size=0.01,
        tick_value_per_lot=1.0,
        progress_interval_bars=progress_interval_bars,
    )
    pipeline = IncrementalPipeline(approve_first=approve_first)
    engine._create_pipeline = lambda: pipeline  # type: ignore[method-assign]
    engine.simulator = NoBatchSimulator(
        tick_size=0.01,
        tick_value_per_lot=1.0,
        breakeven_enabled=False,
    )
    return engine, pipeline


def test_engine_uses_incremental_simulator_without_batch_scan() -> None:
    bars = [
        make_bar(0),
        make_bar(1, open_price=100.0, high=111.0, low=99.5, close=110.0),
        make_bar(2, open_price=110.0, high=111.0, low=109.0, close=110.5),
    ]
    engine, pipeline = make_engine(bars)

    result = engine.run(make_context(bars))

    assert result.total_trades == 1
    assert result.trades[0].entry_time == bars[1].timestamp
    assert result.trades[0].exit_time == bars[1].timestamp
    assert result.trades[0].metadata["simulation_mode"] == (
        "INCREMENTAL_BAR_LIFECYCLE"
    )
    assert pipeline.opened == 1
    assert pipeline.closed == 1
    assert len(pipeline.completed) == 1
    assert engine._active_simulation is None
    assert engine.state.active_trade is None


def test_equity_remains_unrealized_while_incremental_trade_is_open() -> None:
    bars = [
        make_bar(0),
        make_bar(1, open_price=100.0, high=103.0, low=98.0, close=101.0),
        make_bar(2, open_price=101.0, high=104.0, low=99.0, close=102.0),
        make_bar(3, open_price=102.0, high=111.0, low=101.0, close=110.0),
    ]
    engine, pipeline = make_engine(bars)

    result = engine.run(make_context(bars))

    assert [call["account_balance"] for call in pipeline.process_calls] == [
        10_000.0,
        10_000.0,
        10_000.0,
    ]
    assert result.total_trades == 1
    assert result.trades[0].exit_time == bars[3].timestamp
    assert engine.state.current_equity == pytest.approx(
        10_000.0 + result.trades[0].net_profit
    )


def test_open_trade_is_finalized_at_last_processed_bar() -> None:
    bars = [
        make_bar(0),
        make_bar(1, open_price=100.0, high=102.0, low=98.0, close=101.0),
        make_bar(2, open_price=101.0, high=103.0, low=99.0, close=102.0),
    ]
    engine, pipeline = make_engine(bars)

    result = engine.run(make_context(bars))

    assert result.total_trades == 1
    assert result.trades[0].exit_reason is ExitReason.END_OF_DATA
    assert result.trades[0].exit_time == bars[-1].timestamp
    assert pipeline.opened == 1
    assert pipeline.closed == 1


def test_progress_reporting_is_deterministic(capsys: pytest.CaptureFixture[str]) -> None:
    bars = [make_bar(index) for index in range(6)]
    engine, _ = make_engine(
        bars,
        maximum_trades=None,
        progress_interval_bars=2,
        approve_first=False,
    )

    engine.run(make_context(bars))

    output = capsys.readouterr().out
    assert "processed 2/6 bars" in output
    assert "processed 4/6 bars" in output
    assert "processed 6/6 bars" in output


@pytest.mark.parametrize("value", [0, -1])
def test_progress_interval_must_be_positive(value: int) -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        BacktestingEngine(BacktestConfig(), progress_interval_bars=value)


def test_progress_interval_rejects_boolean() -> None:
    with pytest.raises(TypeError, match="integer or None"):
        BacktestingEngine(BacktestConfig(), progress_interval_bars=True)
