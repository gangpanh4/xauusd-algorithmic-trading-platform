from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.backtesting.config import BacktestExecutionModel
from core.backtesting.simulator import TradeSimulator
from core.execution_economics.profiles import (
    pinned_xauusd_research_profile,
)
from core.regime_detector.models import MarketBar
from core.risk_manager.models import RiskDecision, TradePlan
from core.signal_generator.models import SignalDirection, TradingSignal

START = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)


def _bar(
    minute: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
    spread: float | None = None,
) -> MarketBar:
    return MarketBar(
        timestamp=START + timedelta(minutes=minute),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=100.0,
        tick_volume=100,
        spread=spread,
    )


def _plan() -> TradePlan:
    signal = TradingSignal(
        timestamp=START,
        direction=SignalDirection.BUY,
    )
    return TradePlan(
        timestamp=START,
        signal=signal,
        decision=RiskDecision.APPROVE,
        position_size=0.1,
        entry_price=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        risk_reward_ratio=2.0,
    )


def test_trace_records_profile_and_preserves_m15_simulation_contract() -> None:
    profile = pinned_xauusd_research_profile()
    simulator = TradeSimulator(execution_profile=profile)
    observation = _bar(
        0,
        open_price=99.0,
        high=101.0,
        low=98.0,
        close=100.0,
    )
    fill_and_exit = _bar(
        15,
        open_price=101.0,
        high=111.0,
        low=100.0,
        close=110.0,
        spread=999.0,
    )

    trade = simulator.simulate(_plan(), observation, [fill_and_exit])
    trace = trade.metadata["execution_economics_trace"]

    assert trade.entry_time == START + timedelta(minutes=15)
    assert trace["execution_model_id"] == "M15_COMPLETED_OHLC_V1"
    assert trace["entry_policy"] == "NEXT_M15_OPEN"
    assert trace["entry_clock"] == "M15"
    assert trace["decision_clock"] == "M5"
    assert trace["simulation_clock"] == "M15_COMPLETED"
    assert trace["lifecycle_clock"] == "M15_COMPLETED"
    assert trace["lifecycle_bar_minutes"] == 15
    assert trace["closed_bar_consumption"] == "ONLY_AFTER_BAR_COMPLETES"
    assert trace["comparable_with_unversioned_results"] is False
    assert trace["decision_available_at"] == (
        START + timedelta(minutes=5)
    ).isoformat()
    assert trace["decision_timestamp"] == START.isoformat()
    assert trace["intended_entry_timestamp"] == (
        START + timedelta(minutes=15)
    ).isoformat()
    assert trace["actual_entry_timestamp"] == (
        START + timedelta(minutes=15)
    ).isoformat()
    assert trace["historical_price_side"] == "UNKNOWN_SINGLE_PRICE"
    assert trace["historical_specification_verified"] is False
    assert trace["research_sizing_profile"] == "RESEARCH_RISK_PERCENT"
    assert trace["live_sizing_profile"] == "LIVE_CANARY_FIXED_0_01"
    assert trace["parity_claims"]["volume_parity"] is False
    assert set(trace["parity_claims"].values()) == {False}
    assert trade.spread_cost == pytest.approx(0.0)
    assert trade.metadata["historical_spread_field_used"] is False


def test_trace_records_v2_clock_without_changing_execution_economics() -> None:
    profile = pinned_xauusd_research_profile()
    simulator = TradeSimulator(
        execution_profile=profile,
        execution_model=BacktestExecutionModel.M5_COMPLETED_OHLC_V2,
    )
    observation = _bar(
        0,
        open_price=99.0,
        high=101.0,
        low=98.0,
        close=100.0,
    )
    fill_and_exit = _bar(
        5,
        open_price=101.0,
        high=111.0,
        low=100.0,
        close=110.0,
        spread=999.0,
    )

    trade = simulator.simulate(_plan(), observation, [fill_and_exit])
    trace = trade.metadata["execution_economics_trace"]

    assert trade.entry_time == START + timedelta(minutes=5)
    assert trace["execution_model_id"] == "M5_COMPLETED_OHLC_V2"
    assert trace["entry_policy"] == "NEXT_AVAILABLE_M5_OPEN"
    assert trace["entry_clock"] == "M5"
    assert trace["lifecycle_clock"] == "M5_COMPLETED"
    assert trace["simulation_clock"] == "M5_COMPLETED"
    assert trace["lifecycle_bar_minutes"] == 5
    assert trace["decision_available_at"] == (
        START + timedelta(minutes=5)
    ).isoformat()
    assert trace["actual_entry_timestamp"] == (
        START + timedelta(minutes=5)
    ).isoformat()
    assert trace["entry_bar_completed_at"] == (
        START + timedelta(minutes=10)
    ).isoformat()
    assert trace["first_lifecycle_evaluation_available_at"] == (
        START + timedelta(minutes=10)
    ).isoformat()
    assert trace["intra_bar_ambiguity_policy"] == "CONSERVATIVE_STOP_FIRST"
    assert trace["gap_stop_policy"] == "BAR_OPEN_WITH_ADVERSE_SLIPPAGE"
    assert trace["comparable_with_unversioned_results"] is False
    assert trade.spread_cost == pytest.approx(0.0)
    assert trade.metadata["historical_spread_field_used"] is False
