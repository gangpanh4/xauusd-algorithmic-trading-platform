from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from core.backtesting.config import BacktestConfig, LotSizingMode
from core.backtesting.engine import BacktestingEngine
from core.backtesting.models import BacktestTrade, ExitReason, TradeOutcome
from core.feature_engineering.models import FeatureVector
from core.regime_detector.models import MarketBar
from core.risk_manager.config import LotSizingMode as RiskLotSizingMode
from core.risk_manager.models import RiskDecision, TradePlan
from core.signal_generator.models import SignalDirection, TradingSignal
from core.trading_pipeline.market_context import MarketContext


def make_bars(count: int = 4) -> list[MarketBar]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        MarketBar(
            timestamp=start + timedelta(minutes=15 * index),
            open=100.0 + index,
            high=101.0 + index,
            low=99.0 + index,
            close=100.5 + index,
            volume=100.0,
            tick_volume=100,
        )
        for index in range(count)
    ]


def make_context(bars: list[MarketBar]) -> MarketContext:
    return MarketContext(
        current_bar=bars[-1],
        m5_bars=bars,
        m15_bars=bars,
        h1_bars=bars,
        h4_bars=bars,
    )


class FakePipeline:
    def __init__(self) -> None:
        self.process_calls: list[dict[str, object]] = []
        self.balance_syncs: list[tuple[float, datetime | None]] = []
        self.opened = 0
        self.closed = 0
        self.completed: list[tuple[float, datetime | None, float | None]] = []

    def synchronize_account_balance(
        self,
        balance: float,
        *,
        timestamp: datetime | None = None,
    ) -> None:
        self.balance_syncs.append((balance, timestamp))

    def process_bar(self, bar: MarketBar, **kwargs: object) -> SimpleNamespace:
        self.process_calls.append({"bar": bar, **kwargs})
        approved = len(self.process_calls) == 1
        signal = TradingSignal(
            timestamp=bar.timestamp,
            direction=SignalDirection.BUY if approved else SignalDirection.HOLD,
        )
        plan = TradePlan(
            timestamp=bar.timestamp,
            signal=signal,
            decision=RiskDecision.APPROVE if approved else RiskDecision.SKIP,
            position_size=0.10 if approved else 0.0,
            entry_price=bar.close,
            stop_loss=bar.close - 2.5,
            take_profit=bar.close + 5.0,
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


class FakeSimulator:
    def simulate(
        self,
        *,
        trade_plan: TradePlan,
        entry_bar: MarketBar,
        future_bars: list[MarketBar],
    ) -> BacktestTrade:
        exit_bar = future_bars[1]
        return BacktestTrade(
            entry_time=entry_bar.timestamp,
            exit_time=exit_bar.timestamp,
            direction="BUY",
            entry_price=trade_plan.entry_price,
            exit_price=trade_plan.entry_price + 1.0,
            position_size=trade_plan.position_size,
            gross_profit=100.0,
            net_profit=100.0,
            outcome=TradeOutcome.WIN,
            exit_reason=ExitReason.TAKE_PROFIT,
            holding_bars=2,
        )


def test_engine_defers_realized_pnl_until_exit_and_forwards_symbol_inputs() -> None:
    bars = make_bars(4)
    config = BacktestConfig(warmup_bars=0, maximum_trades=1)
    engine = BacktestingEngine(
        config,
        stop_loss_distance=3.0,
        tick_size=0.01,
        tick_value_per_lot=1.25,
        lot_step=0.001,
    )
    pipeline = FakePipeline()
    engine._create_pipeline = lambda: pipeline  # type: ignore[method-assign]
    engine.simulator = FakeSimulator()

    result = engine.run(make_context(bars))

    assert pipeline.balance_syncs == [(10_000.0, bars[0].timestamp)]
    assert [call["account_balance"] for call in pipeline.process_calls] == [
        10_000.0,
        10_000.0,
    ]
    assert pipeline.process_calls[0]["stop_loss_distance"] == 3.0
    assert pipeline.process_calls[0]["pip_value"] == 1.25
    assert pipeline.process_calls[0]["tick_size"] == 0.01
    assert pipeline.process_calls[0]["lot_step"] == 0.001
    assert pipeline.opened == 1
    assert pipeline.closed == 1
    assert pipeline.completed == [(100.0, bars[2].timestamp, 10_100.0)]
    assert result.total_trades == 1
    assert result.net_profit == 100.0
    assert engine.state.current_equity == 10_100.0


def test_engine_applies_backtest_config_precedence_to_pipeline_risk() -> None:
    config = BacktestConfig(
        lot_mode=LotSizingMode.RISK_PERCENT,
        fixed_lot_size=0.02,
        risk_percent=0.5,
        use_virtual_balance=True,
        virtual_balance=250.0,
        max_open_positions=1,
        spread_points=12.0,
        commission_per_lot=7.5,
        slippage_points=3.0,
    )
    engine = BacktestingEngine(config)

    effective = engine._build_pipeline_config().risk_manager

    assert effective.lot_sizing_mode == RiskLotSizingMode.RISK_PERCENT
    assert effective.fixed_lot_size == 0.02
    assert effective.risk_percent == 0.5
    assert effective.use_virtual_balance is True
    assert effective.virtual_balance == 250.0
    assert effective.maximum_open_positions == 1
    assert effective.allow_multiple_positions is False
    assert effective.spread_points == 12.0
    assert effective.commission_per_lot == 7.5
    assert effective.slippage_points == 3.0



def test_engine_rejects_unsupported_multiple_position_configuration() -> None:
    with pytest.raises(ValueError, match="exactly one active position"):
        BacktestingEngine(BacktestConfig(max_open_positions=2))

def test_engine_rejects_duplicate_or_unsorted_historical_timestamps() -> None:
    bars = make_bars(3)
    bars[2] = replace(bars[2], timestamp=bars[1].timestamp)
    engine = BacktestingEngine(BacktestConfig(warmup_bars=0))

    with pytest.raises(ValueError, match="strictly increasing"):
        engine.run(make_context(bars))


def test_engine_does_not_execute_signal_on_final_bar_without_future_data() -> None:
    bars = make_bars(1)
    config = BacktestConfig(warmup_bars=0)
    engine = BacktestingEngine(config)
    pipeline = FakePipeline()
    engine._create_pipeline = lambda: pipeline  # type: ignore[method-assign]
    engine.simulator = FakeSimulator()

    result = engine.run(make_context(bars))

    assert result.total_trades == 0
    assert pipeline.opened == 0
    assert pipeline.closed == 0
    assert pipeline.completed == []


def test_engine_resets_pipeline_and_research_state_between_runs() -> None:
    bars = make_bars(4)
    config = BacktestConfig(warmup_bars=0, maximum_trades=1)
    engine = BacktestingEngine(config)
    pipelines: list[FakePipeline] = []

    def factory() -> FakePipeline:
        pipeline = FakePipeline()
        pipelines.append(pipeline)
        return pipeline

    engine._create_pipeline = factory  # type: ignore[method-assign]
    engine.simulator = FakeSimulator()

    first = engine.run(make_context(bars))
    second = engine.run(make_context(bars))

    assert first.total_trades == 1
    assert second.total_trades == 1
    assert engine.research_storage.total_trades == 1
    assert len(pipelines) == 2
