from datetime import UTC, datetime

import pytest

from core.risk_manager.config import LotSizingMode, RiskManagerConfig
from core.risk_manager.manager import RiskManager
from core.risk_manager.models import RiskDecision
from core.signal_generator.models import (
    SignalStrength,
    SignalType,
    TradingSignal,
)


def _buy_signal() -> TradingSignal:
    return TradingSignal(
        timestamp=datetime.now(UTC),
        signal=SignalType.BUY,
        strength=SignalStrength.STRONG,
        confidence=0.90,
        reason="Risk manager test",
    )


def _evaluate(
    config: RiskManagerConfig,
    *,
    stop_loss_distance: float = 100.0,
    pip_value: float = 1.0,
    tick_size: float = 1.0,
):
    return RiskManager(config).evaluate_signal(
        signal=_buy_signal(),
        entry_price=3300.0,
        account_balance=10_000.0,
        stop_loss_distance=stop_loss_distance,
        pip_value=pip_value,
        tick_size=tick_size,
    )


def test_risk_manager():
    config = RiskManagerConfig(
        debug_logging=True,
    )

    manager = RiskManager(config)

    signal = TradingSignal(
        timestamp=datetime.now(UTC),
        signal=SignalType.BUY,
        strength=SignalStrength.STRONG,
        confidence=0.90,
        reason="Integration Test",
    )

    entry_price = 3300.00

    trade_plan = manager.evaluate_signal(
        signal=signal,
        entry_price=entry_price,
        account_balance=10000.0,
        stop_loss_distance=250.0,
        pip_value=1.0,
    )

    assert trade_plan.decision == RiskDecision.APPROVE
    assert trade_plan.entry_price == entry_price
    assert trade_plan.position_size > 0.0
    assert trade_plan.stop_loss < entry_price
    assert trade_plan.take_profit > entry_price
    assert trade_plan.risk_reward_ratio >= 2.0


def test_zero_cost_risk_percent_sizing_preserves_existing_result():
    plan = _evaluate(
        RiskManagerConfig(
            lot_sizing_mode=LotSizingMode.RISK_PERCENT,
            risk_percent=1.0,
            spread_points=0.0,
            slippage_points=0.0,
            commission_per_lot=0.0,
        )
    )

    assert plan.decision is RiskDecision.APPROVE
    assert plan.position_size == pytest.approx(1.0)
    assert plan.metadata["price_risk"] == pytest.approx(100.0)
    assert plan.metadata["total_monetary_risk"] == pytest.approx(100.0)


def test_costs_reduce_risk_percent_position_size():
    plan = _evaluate(
        RiskManagerConfig(
            lot_sizing_mode=LotSizingMode.RISK_PERCENT,
            risk_percent=1.0,
            spread_points=10.0,
            slippage_points=5.0,
            commission_per_lot=10.0,
        )
    )

    assert plan.decision is RiskDecision.APPROVE
    assert plan.position_size == pytest.approx(0.76)
    assert plan.metadata["price_risk"] == pytest.approx(76.0)
    assert plan.metadata["spread_risk"] == pytest.approx(7.6)
    assert plan.metadata["slippage_risk"] == pytest.approx(7.6)
    assert plan.metadata["commission_risk"] == pytest.approx(7.6)
    assert plan.metadata["total_monetary_risk"] == pytest.approx(98.8)
    assert plan.risk_percent == pytest.approx(0.988)


def test_spread_and_commission_flags_disable_their_costs():
    plan = _evaluate(
        RiskManagerConfig(
            lot_sizing_mode=LotSizingMode.RISK_PERCENT,
            risk_percent=1.0,
            include_spread=False,
            spread_points=50.0,
            slippage_points=5.0,
            include_commission=False,
            commission_per_lot=50.0,
        )
    )

    assert plan.decision is RiskDecision.APPROVE
    assert plan.position_size == pytest.approx(0.90)
    assert plan.metadata["spread_risk"] == pytest.approx(0.0)
    assert plan.metadata["commission_risk"] == pytest.approx(0.0)
    assert plan.metadata["slippage_risk"] == pytest.approx(9.0)
    assert plan.metadata["total_monetary_risk"] == pytest.approx(99.0)


def test_slippage_reserves_entry_and_stop_exit_cost():
    plan = _evaluate(
        RiskManagerConfig(
            lot_sizing_mode=LotSizingMode.RISK_PERCENT,
            risk_percent=1.0,
            include_spread=False,
            include_commission=False,
            slippage_points=10.0,
        )
    )

    assert plan.decision is RiskDecision.APPROVE
    assert plan.position_size == pytest.approx(0.83)
    assert plan.metadata["slippage_risk"] == pytest.approx(16.6)
    assert plan.metadata["total_monetary_risk"] == pytest.approx(99.6)


def test_fixed_lot_rejects_when_total_economic_risk_exceeds_limit():
    plan = _evaluate(
        RiskManagerConfig(
            lot_sizing_mode=LotSizingMode.FIXED,
            fixed_lot_size=1.0,
            max_risk_per_trade=0.01,
            spread_points=10.0,
            slippage_points=5.0,
            commission_per_lot=10.0,
        )
    )

    assert plan.decision is RiskDecision.REJECT
    assert plan.position_size == 0.0
    assert "actual monetary risk exceeds" in plan.reason


def test_cost_aware_sizing_floors_to_lot_step_without_exceeding_limit():
    plan = RiskManager(
        RiskManagerConfig(
            lot_sizing_mode=LotSizingMode.RISK_PERCENT,
            risk_percent=1.0,
            spread_points=3.0,
            slippage_points=2.0,
            commission_per_lot=4.0,
        )
    ).evaluate_signal(
        signal=_buy_signal(),
        entry_price=3300.0,
        account_balance=10_000.0,
        stop_loss_distance=100.0,
        pip_value=1.0,
        tick_size=1.0,
        lot_step=0.05,
    )

    assert plan.decision is RiskDecision.APPROVE
    assert plan.position_size == pytest.approx(0.86)
    assert plan.metadata["total_monetary_risk"] == pytest.approx(95.46)
    assert plan.metadata["total_monetary_risk"] <= 100.0
    assert plan.risk_percent <= 1.0


def test_runtime_broker_minimum_rejects_smaller_risk_size():
    plan = RiskManager(
        RiskManagerConfig(
            lot_sizing_mode=LotSizingMode.RISK_PERCENT,
            risk_percent=1.0,
            minimum_position_size=0.01,
            maximum_position_size=10.0,
        )
    ).evaluate_signal(
        signal=_buy_signal(),
        entry_price=3300.0,
        account_balance=1000.0,
        stop_loss_distance=1000.0,
        pip_value=1.0,
        tick_size=1.0,
        lot_step=0.01,
        minimum_lot=0.10,
        maximum_lot=25.0,
    )

    assert plan.decision is RiskDecision.REJECT
    assert plan.position_size == 0.0
    assert "below the broker minimum" in plan.reason


def test_runtime_broker_maximum_caps_position_size():
    plan = RiskManager(
        RiskManagerConfig(
            lot_sizing_mode=LotSizingMode.RISK_PERCENT,
            risk_percent=1.0,
            minimum_position_size=0.01,
            maximum_position_size=10.0,
        )
    ).evaluate_signal(
        signal=_buy_signal(),
        entry_price=3300.0,
        account_balance=100_000.0,
        stop_loss_distance=10.0,
        pip_value=1.0,
        tick_size=1.0,
        lot_step=0.01,
        minimum_lot=0.01,
        maximum_lot=2.0,
    )

    assert plan.decision is RiskDecision.APPROVE
    assert plan.position_size == pytest.approx(2.0)
    assert plan.metadata["minimum_lot"] == pytest.approx(0.01)
    assert plan.metadata["maximum_lot"] == pytest.approx(2.0)
