from datetime import UTC, datetime

from core.risk_manager.config import RiskManagerConfig
from core.risk_manager.manager import RiskManager
from core.risk_manager.models import RiskDecision
from core.signal_generator.models import (
    SignalStrength,
    SignalType,
    TradingSignal,
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

    print()
    print("========== TRADE PLAN ==========")

    print(f"Decision      : {trade_plan.decision.value}")
    print(f"Entry Price   : {trade_plan.entry_price:.2f}")
    print(f"Stop Loss     : {trade_plan.stop_loss:.2f}")
    print(f"Take Profit   : {trade_plan.take_profit:.2f}")
    print(f"Position Size : {trade_plan.position_size:.2f}")
    print(f"Risk          : {trade_plan.risk_percent:.2f}%")
    print(f"Reward        : {trade_plan.reward_percent:.2f}%")
    print(f"R:R           : {trade_plan.risk_reward_ratio:.2f}")
    print(f"Reason        : {trade_plan.reason}")

    assert trade_plan.decision == RiskDecision.APPROVE

    assert trade_plan.entry_price == entry_price

    assert trade_plan.position_size > 0.0

    assert trade_plan.stop_loss < entry_price

    assert trade_plan.take_profit > entry_price

    assert trade_plan.risk_reward_ratio >= 2.0


if __name__ == "__main__":
    test_risk_manager()