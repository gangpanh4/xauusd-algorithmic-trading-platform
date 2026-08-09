from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from core.backtesting.config import BacktestConfig
from core.backtesting.engine import BacktestingEngine
from core.execution_economics.profiles import (
    pinned_xauusd_research_profile,
)
from core.feature_engineering.models import FeatureVector
from core.regime_detector.models import MarketBar
from core.risk_manager.models import RiskDecision, TradePlan
from core.signal_generator.models import SignalDirection, TradingSignal
from core.trading_pipeline.market_context import MarketContext

BASE_TIME = datetime(2025, 1, 1, tzinfo=UTC)


def make_bar(
    index: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
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


class CostIntegrationPipeline:
    def __init__(self) -> None:
        self.calls = 0
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

    def process_bar(self, bar: MarketBar, **_: object) -> SimpleNamespace:
        self.calls += 1
        approved = self.calls == 1
        signal = TradingSignal(
            timestamp=bar.timestamp,
            direction=(SignalDirection.BUY if approved else SignalDirection.HOLD),
        )
        plan = TradePlan(
            timestamp=bar.timestamp,
            signal=signal,
            decision=(RiskDecision.APPROVE if approved else RiskDecision.SKIP),
            position_size=0.1 if approved else 0.0,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            risk_reward_ratio=2.0,
            probability=0.7,
            confidence=0.8,
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


def make_context() -> MarketContext:
    bars = [
        make_bar(0, open_price=99.0, high=101.0, low=98.0, close=100.0),
        make_bar(1, open_price=100.0, high=110.5, low=99.5, close=110.0),
        make_bar(2, open_price=110.0, high=111.0, low=109.0, close=110.5),
    ]
    return MarketContext(
        current_bar=bars[-1],
        m5_bars=bars,
        m15_bars=bars,
        h1_bars=bars,
        h4_bars=bars,
    )


def test_engine_constructs_simulator_from_backtest_cost_config() -> None:
    config = BacktestConfig(
        spread_points=2.0,
        slippage_points=1.0,
        commission_per_trade=0.5,
        commission_per_lot=2.0,
    )

    engine = BacktestingEngine(
        config,
        tick_size=0.01,
        tick_value_per_lot=1.25,
    )

    assert engine.simulator._tick_size == pytest.approx(0.01)
    assert engine.simulator._tick_value_per_lot == pytest.approx(1.25)
    assert engine.simulator._spread_points == pytest.approx(2.0)
    assert engine.simulator._slippage_points == pytest.approx(1.0)
    assert engine.simulator._commission_per_trade == pytest.approx(0.5)
    assert engine.simulator._commission_per_lot == pytest.approx(2.0)


def test_explicit_execution_profile_is_authoritative_in_engine() -> None:
    profile = pinned_xauusd_research_profile()
    config = BacktestConfig(
        execution_profile=profile,
        tick_size=99.0,
        tick_value_per_lot=99.0,
        spread_points=99.0,
    )

    engine = BacktestingEngine(config)

    assert engine.execution_profile is profile
    assert engine.tick_size == pytest.approx(profile.instrument.tick_size)
    assert engine.tick_value_per_lot == pytest.approx(
        profile.instrument.tick_value_per_lot
    )
    assert engine.simulator.execution_profile is profile
    assert engine.simulator._spread_points == pytest.approx(
        profile.costs.spread_points
    )


def test_engine_applies_configured_costs_to_full_backtest_trade() -> None:
    config = BacktestConfig(
        warmup_bars=0,
        maximum_trades=1,
        spread_points=2.0,
        slippage_points=1.0,
        commission_per_trade=0.5,
        commission_per_lot=2.0,
    )
    engine = BacktestingEngine(
        config,
        tick_size=0.01,
        tick_value_per_lot=1.0,
    )
    pipeline = CostIntegrationPipeline()
    engine._create_pipeline = lambda: pipeline  # type: ignore[method-assign]

    result = engine.run(make_context())

    assert result.total_trades == 1
    trade = result.trades[0]
    assert trade.entry_price == pytest.approx(100.01)
    assert trade.exit_price == pytest.approx(110.0)
    assert trade.gross_profit == pytest.approx(99.9)
    assert trade.spread_cost == pytest.approx(0.2)
    assert trade.commission == pytest.approx(0.7)
    assert trade.net_profit == pytest.approx(99.0)
    assert result.net_profit == pytest.approx(99.0)
    assert pipeline.opened == 1
    assert pipeline.closed == 1
    assert pipeline.completed == [
        (pytest.approx(99.0), BASE_TIME + timedelta(minutes=15), pytest.approx(10_099.0))
    ]
