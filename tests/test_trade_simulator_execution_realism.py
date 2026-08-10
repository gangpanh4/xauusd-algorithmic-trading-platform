from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.backtesting.config import BacktestExecutionModel
from core.backtesting.models import ExitReason, TradeOutcome
from core.backtesting.simulator import ExecutionPolicy, TradeSimulator
from core.regime_detector.models import MarketBar
from core.risk_manager.models import RiskDecision, TradePlan
from core.signal_generator.models import SignalDirection, TradingSignal

BASE_TIME = datetime(2025, 1, 1, tzinfo=UTC)


def make_bar(
    minute: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
    spread: float | None = None,
) -> MarketBar:
    return MarketBar(
        timestamp=BASE_TIME + timedelta(minutes=minute),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=100.0,
        spread=spread,
        tick_volume=100,
    )


def make_plan(
    direction: SignalDirection = SignalDirection.BUY,
    *,
    entry: float = 100.0,
    stop: float | None = None,
    target: float | None = None,
    position_size: float = 0.1,
    metadata: dict | None = None,
) -> TradePlan:
    if stop is None:
        stop = 95.0 if direction is SignalDirection.BUY else 105.0
    if target is None:
        target = 110.0 if direction is SignalDirection.BUY else 90.0
    signal = TradingSignal(
        timestamp=BASE_TIME,
        direction=direction,
        confidence=0.8,
    )
    return TradePlan(
        timestamp=BASE_TIME,
        signal=signal,
        decision=RiskDecision.APPROVE,
        position_size=position_size,
        entry_price=entry,
        stop_loss=stop,
        take_profit=target,
        risk_reward_ratio=2.0,
        metadata={
            "tick_size": 0.01,
            "tick_value_per_lot": 1.0,
            **(metadata or {}),
        },
    )


def test_buy_enters_at_next_bar_open_and_uses_tick_value_pnl() -> None:
    observation = make_bar(0, open_price=99.0, high=101.0, low=98.0, close=100.0)
    fill_and_exit = make_bar(
        15,
        open_price=101.0,
        high=111.5,
        low=100.5,
        close=111.0,
    )

    trade = TradeSimulator().simulate(
        make_plan(),
        observation,
        [fill_and_exit],
    )

    assert trade.entry_time == fill_and_exit.timestamp
    assert trade.entry_price == pytest.approx(101.0)
    assert trade.exit_price == pytest.approx(111.0)
    assert trade.gross_profit == pytest.approx(100.0)
    assert trade.net_profit == pytest.approx(100.0)
    assert trade.exit_reason is ExitReason.TAKE_PROFIT
    assert trade.outcome is TradeOutcome.WIN
    assert trade.metadata["entry_policy"] == "NEXT_M15_OPEN"
    assert trade.metadata["execution_model_id"] == "M15_COMPLETED_OHLC_V1"
    assert trade.metadata["effective_stop_loss"] == pytest.approx(96.0)
    assert trade.metadata["effective_take_profit"] == pytest.approx(111.0)


def test_spread_commission_and_slippage_reduce_net_profit() -> None:
    observation = make_bar(0, open_price=99.0, high=101.0, low=98.0, close=100.0)
    fill_and_exit = make_bar(
        15,
        open_price=100.0,
        high=110.5,
        low=99.5,
        close=110.0,
    )
    plan = make_plan(
        metadata={
            "spread_points": 2.0,
            "slippage_points": 1.0,
            "commission_per_trade": 0.5,
            "commission_per_lot": 2.0,
        }
    )

    trade = TradeSimulator().simulate(plan, observation, [fill_and_exit])

    assert trade.entry_price == pytest.approx(100.01)
    assert trade.exit_price == pytest.approx(110.0)
    assert trade.gross_profit == pytest.approx(99.9)
    assert trade.spread_cost == pytest.approx(0.2)
    assert trade.commission == pytest.approx(0.7)
    assert trade.net_profit == pytest.approx(99.0)
    assert trade.metadata["slippage_cost"] == pytest.approx(0.1)


def test_v1_and_v2_keep_identical_execution_economics_for_same_ohlc() -> None:
    observation = make_bar(0, open_price=99.0, high=101.0, low=98.0, close=100.0)
    v1_bar = make_bar(15, open_price=100.0, high=110.5, low=99.5, close=110.0)
    v2_bar = make_bar(5, open_price=100.0, high=110.5, low=99.5, close=110.0)
    plan = make_plan(
        metadata={
            "spread_points": 2.0,
            "slippage_points": 1.0,
            "commission_per_trade": 0.5,
            "commission_per_lot": 2.0,
        }
    )

    v1 = TradeSimulator(
        execution_model=BacktestExecutionModel.M15_COMPLETED_OHLC_V1
    ).simulate(plan, observation, [v1_bar])
    v2 = TradeSimulator(
        execution_model=BacktestExecutionModel.M5_COMPLETED_OHLC_V2
    ).simulate(plan, observation, [v2_bar])

    assert v1.entry_price == pytest.approx(v2.entry_price)
    assert v1.exit_price == pytest.approx(v2.exit_price)
    assert v1.gross_profit == pytest.approx(v2.gross_profit)
    assert v1.spread_cost == pytest.approx(v2.spread_cost)
    assert v1.commission == pytest.approx(v2.commission)
    assert v1.net_profit == pytest.approx(v2.net_profit)
    assert v1.metadata["exit_levels_recentered"] is True
    assert v2.metadata["exit_levels_recentered"] is True
    assert v1.metadata["execution_model_id"] == "M15_COMPLETED_OHLC_V1"
    assert v2.metadata["execution_model_id"] == "M5_COMPLETED_OHLC_V2"


def test_historical_bar_spread_is_not_used_for_execution_economics() -> None:
    observation = make_bar(
        0,
        open_price=99.0,
        high=101.0,
        low=98.0,
        close=100.0,
    )
    fill_and_exit = make_bar(
        15,
        open_price=100.0,
        high=110.5,
        low=99.5,
        close=110.0,
        spread=250.0,
    )

    trade = TradeSimulator().simulate(
        make_plan(),
        observation,
        [fill_and_exit],
    )

    assert trade.spread_cost == pytest.approx(0.0)
    assert trade.metadata["historical_spread_field_used"] is False


def test_buy_gap_through_stop_exits_at_open_with_adverse_slippage() -> None:
    observation = make_bar(0, open_price=99.0, high=101.0, low=98.0, close=100.0)
    fill = make_bar(15, open_price=100.0, high=104.0, low=99.0, close=103.0)
    gap = make_bar(30, open_price=94.0, high=95.0, low=93.0, close=94.0)
    simulator = TradeSimulator(slippage_points=1.0)

    trade = simulator.simulate(make_plan(), observation, [fill, gap])

    assert trade.exit_reason is ExitReason.STOP_LOSS
    assert trade.exit_price == pytest.approx(93.99)
    assert trade.gross_profit == pytest.approx(-60.2)
    assert "GAP_EXIT" in trade.lifecycle_events
    assert trade.outcome is TradeOutcome.LOSS


def test_ambiguous_bar_uses_configured_execution_policy() -> None:
    observation = make_bar(0, open_price=99.0, high=101.0, low=98.0, close=100.0)
    ambiguous = make_bar(
        15,
        open_price=100.0,
        high=111.0,
        low=94.0,
        close=100.0,
    )
    plan = make_plan()

    conservative = TradeSimulator(ExecutionPolicy.CONSERVATIVE).simulate(
        plan,
        observation,
        [ambiguous],
    )
    optimistic = TradeSimulator(ExecutionPolicy.OPTIMISTIC).simulate(
        plan,
        observation,
        [ambiguous],
    )

    assert conservative.exit_reason is ExitReason.STOP_LOSS
    assert conservative.net_profit == pytest.approx(-50.0)
    assert optimistic.exit_reason is ExitReason.TAKE_PROFIT
    assert optimistic.net_profit == pytest.approx(100.0)


def test_sell_direction_uses_symmetric_tick_economics() -> None:
    observation = make_bar(0, open_price=101.0, high=102.0, low=99.0, close=100.0)
    fill_and_exit = make_bar(
        15,
        open_price=99.0,
        high=99.5,
        low=88.5,
        close=89.0,
    )

    trade = TradeSimulator().simulate(
        make_plan(SignalDirection.SELL),
        observation,
        [fill_and_exit],
    )

    assert trade.entry_price == pytest.approx(99.0)
    assert trade.exit_price == pytest.approx(89.0)
    assert trade.gross_profit == pytest.approx(100.0)
    assert trade.direction == "SELL"
    assert trade.outcome is TradeOutcome.WIN


def test_breakeven_activates_on_next_bar_only() -> None:
    observation = make_bar(0, open_price=99.0, high=101.0, low=98.0, close=100.0)
    reaches_one_r = make_bar(
        15,
        open_price=100.0,
        high=105.0,
        low=99.0,
        close=104.0,
    )
    returns_to_entry = make_bar(
        30,
        open_price=104.0,
        high=104.5,
        low=99.0,
        close=100.0,
    )

    trade = TradeSimulator().simulate(
        make_plan(),
        observation,
        [reaches_one_r, returns_to_entry],
    )

    assert trade.breakeven_triggered is True
    assert trade.exit_reason is ExitReason.STOP_LOSS
    assert trade.exit_price == pytest.approx(100.0)
    assert trade.net_profit == pytest.approx(0.0)
    assert trade.outcome is TradeOutcome.BREAKEVEN
    assert trade.lifecycle_events == (
        "ENTRY_NEXT_BAR_OPEN",
        "BREAKEVEN_PENDING",
        "BREAKEVEN_ACTIVE",
        "STOP_LOSS",
    )


def test_end_of_data_closes_at_last_close() -> None:
    observation = make_bar(0, open_price=99.0, high=101.0, low=98.0, close=100.0)
    only_bar = make_bar(
        15,
        open_price=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
    )

    trade = TradeSimulator(breakeven_enabled=False).simulate(
        make_plan(),
        observation,
        [only_bar],
    )

    assert trade.exit_reason is ExitReason.END_OF_DATA
    assert trade.exit_price == pytest.approx(101.0)
    assert trade.gross_profit == pytest.approx(10.0)
    assert trade.holding_bars == 1
    assert trade.holding_time == timedelta(0)


def test_invalid_future_bar_sequence_fails_closed() -> None:
    observation = make_bar(0, open_price=99.0, high=101.0, low=98.0, close=100.0)
    duplicate = make_bar(0, open_price=100.0, high=101.0, low=99.0, close=100.0)

    with pytest.raises(ValueError, match="strictly later"):
        TradeSimulator().simulate(make_plan(), observation, [duplicate])

    with pytest.raises(ValueError, match="at least one"):
        TradeSimulator().simulate(make_plan(), observation, [])
