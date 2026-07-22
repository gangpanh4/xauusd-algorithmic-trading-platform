from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.backtesting.models import ExitReason
from core.backtesting.simulator import (
    IncrementalTradeSimulation,
    SimulationPhase,
    TradeSimulator,
)
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
) -> MarketBar:
    return MarketBar(
        timestamp=BASE_TIME + timedelta(minutes=minute),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=100.0,
        tick_volume=100,
    )


def make_plan() -> TradePlan:
    signal = TradingSignal(
        timestamp=BASE_TIME,
        direction=SignalDirection.BUY,
        confidence=0.8,
    )
    return TradePlan(
        timestamp=BASE_TIME,
        signal=signal,
        decision=RiskDecision.APPROVE,
        position_size=0.1,
        entry_price=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        risk_reward_ratio=2.0,
        metadata={
            "tick_size": 0.01,
            "tick_value_per_lot": 1.0,
            "spread_points": 1.0,
            "slippage_points": 1.0,
            "commission_per_trade": 0.25,
        },
    )


def test_begin_creates_pending_trade_without_a_future_bar() -> None:
    observation = make_bar(
        0,
        open_price=99.0,
        high=101.0,
        low=98.0,
        close=100.0,
    )

    simulation = TradeSimulator().begin(make_plan(), observation)

    assert isinstance(simulation, IncrementalTradeSimulation)
    assert simulation.phase is SimulationPhase.PENDING_ENTRY
    assert simulation.fill_bar is None
    assert simulation.state is None
    assert simulation.completed_trade is None


def test_process_bar_fills_then_closes_incrementally() -> None:
    simulator = TradeSimulator()
    observation = make_bar(
        0,
        open_price=99.0,
        high=101.0,
        low=98.0,
        close=100.0,
    )
    fill = make_bar(
        15,
        open_price=100.0,
        high=103.0,
        low=99.0,
        close=102.0,
    )
    target = make_bar(
        30,
        open_price=102.0,
        high=111.0,
        low=101.0,
        close=110.0,
    )
    simulation = simulator.begin(make_plan(), observation)

    assert simulator.process_bar(simulation, fill) is None
    assert simulation.phase is SimulationPhase.OPEN
    assert simulation.fill_bar == fill
    assert simulation.state is not None
    assert simulation.state.holding_bars == 1

    trade = simulator.process_bar(simulation, target)

    assert trade is not None
    assert simulation.phase is SimulationPhase.CLOSED
    assert simulation.completed_trade == trade
    assert trade.exit_reason is ExitReason.TAKE_PROFIT
    assert trade.holding_bars == 2
    assert trade.metadata["simulation_mode"] == "INCREMENTAL_BAR_LIFECYCLE"


def test_batch_wrapper_matches_incremental_lifecycle_exactly() -> None:
    observation = make_bar(
        0,
        open_price=99.0,
        high=101.0,
        low=98.0,
        close=100.0,
    )
    bars = [
        make_bar(
            15,
            open_price=100.0,
            high=105.0,
            low=99.0,
            close=104.0,
        ),
        make_bar(
            30,
            open_price=104.0,
            high=104.5,
            low=99.0,
            close=100.0,
        ),
    ]

    batch = TradeSimulator().simulate(make_plan(), observation, bars)

    simulator = TradeSimulator()
    simulation = simulator.begin(make_plan(), observation)
    incremental = None
    for bar in bars:
        incremental = simulator.process_bar(simulation, bar)
        if incremental is not None:
            break
    if incremental is None:
        incremental = simulator.finalize_at_end_of_data(simulation)

    assert incremental == batch


def test_finalize_at_end_of_data_is_idempotent_after_close() -> None:
    simulator = TradeSimulator(breakeven_enabled=False)
    observation = make_bar(
        0,
        open_price=99.0,
        high=101.0,
        low=98.0,
        close=100.0,
    )
    final_bar = make_bar(
        15,
        open_price=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
    )
    simulation = simulator.begin(make_plan(), observation)

    assert simulator.process_bar(simulation, final_bar) is None
    trade = simulator.finalize_at_end_of_data(simulation)

    assert trade.exit_reason is ExitReason.END_OF_DATA
    assert simulator.finalize_at_end_of_data(simulation) is trade


def test_incremental_lifecycle_rejects_invalid_ordering_and_reuse() -> None:
    simulator = TradeSimulator()
    observation = make_bar(
        0,
        open_price=99.0,
        high=101.0,
        low=98.0,
        close=100.0,
    )
    target = make_bar(
        15,
        open_price=100.0,
        high=111.0,
        low=99.0,
        close=110.0,
    )
    simulation = simulator.begin(make_plan(), observation)

    with pytest.raises(ValueError, match="strictly later"):
        simulator.process_bar(simulation, observation)

    completed = simulator.process_bar(simulation, target)
    assert completed is not None

    with pytest.raises(RuntimeError, match="closed"):
        simulator.process_bar(
            simulation,
            make_bar(
                30,
                open_price=110.0,
                high=111.0,
                low=109.0,
                close=110.0,
            ),
        )


def test_pending_simulation_cannot_be_finalized_without_fill() -> None:
    observation = make_bar(
        0,
        open_price=99.0,
        high=101.0,
        low=98.0,
        close=100.0,
    )
    simulator = TradeSimulator()
    simulation = simulator.begin(make_plan(), observation)

    with pytest.raises(ValueError, match="before a market-entry bar"):
        simulator.finalize_at_end_of_data(simulation)
