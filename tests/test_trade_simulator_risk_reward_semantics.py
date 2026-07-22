from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.backtesting.models import ExitReason
from core.backtesting.simulator import TradeSimulator
from core.regime_detector.models import MarketBar
from core.risk_manager.models import RiskDecision, TradePlan
from core.signal_generator.models import SignalDirection, TradingSignal


def _bar(minutes: int, *, open_: float, high: float, low: float, close: float) -> MarketBar:
    return MarketBar(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=minutes),
        open=open_, high=high, low=low, close=close, volume=100.0,
    )


def _plan(direction: SignalDirection) -> TradePlan:
    is_buy = direction is SignalDirection.BUY
    return TradePlan(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        decision=RiskDecision.APPROVE,
        signal=TradingSignal(direction=direction),
        entry_price=100.0,
        stop_loss=95.0 if is_buy else 105.0,
        take_profit=110.0 if is_buy else 90.0,
        position_size=1.0,
        risk_percent=1.0,
        reward_percent=2.0,
        risk_reward_ratio=2.0,
        reason="test",
    )


def test_trade_risk_reward_reports_planned_ratio_on_stop_loss() -> None:
    simulator = TradeSimulator()
    simulation = simulator.begin(_plan(SignalDirection.SELL), _bar(0, open_=100, high=101, low=99, close=100))

    trade = simulator.process_bar(
        simulation,
        _bar(15, open_=100, high=106, low=99, close=104),
    )

    assert trade is not None
    assert trade.exit_reason is ExitReason.STOP_LOSS
    assert trade.risk_reward == pytest.approx(2.0)
    assert trade.metadata["planned_risk_reward_ratio"] == pytest.approx(2.0)
    assert trade.metadata["realized_gross_r_multiple"] == pytest.approx(-1.0)
    assert trade.metadata["same_bar_exit"] is True


def test_trade_risk_reward_reports_planned_ratio_on_take_profit() -> None:
    simulator = TradeSimulator()
    simulation = simulator.begin(_plan(SignalDirection.BUY), _bar(0, open_=100, high=101, low=99, close=100))

    trade = simulator.process_bar(
        simulation,
        _bar(15, open_=100, high=111, low=99, close=110),
    )

    assert trade is not None
    assert trade.exit_reason is ExitReason.TAKE_PROFIT
    assert trade.risk_reward == pytest.approx(2.0)
    assert trade.metadata["planned_risk_reward_ratio"] == pytest.approx(2.0)
    assert trade.metadata["realized_gross_r_multiple"] == pytest.approx(2.0)
