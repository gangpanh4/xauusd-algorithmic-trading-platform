from datetime import datetime, UTC

from core.signal_generator.models import (
    SignalStrength,
    SignalType,
    TradingSignal,
)

from core.risk_manager.config import (
    RiskManagerConfig,
)

from core.risk_manager.manager import (
    RiskManager,
)

from core.risk_manager.models import (
    RiskDecision,
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

    trade_plan = manager.evaluate_signal(
        signal=signal,
        account_balance=10000.0,
        stop_loss_distance=250.0,
        pip_value=1.0,
    )

    print()
    print("========== TRADE PLAN ==========")

    print(f"Decision      : {trade_plan.decision.value}")
    print(f"Position Size : {trade_plan.position_size:.2f}")
    print(f"Risk          : {trade_plan.risk_percent:.2%}")
    print(f"Reward        : {trade_plan.reward_percent:.2%}")
    print(f"R:R           : {trade_plan.risk_reward_ratio:.2f}")
    print(f"Reason        : {trade_plan.reason}")

    assert trade_plan.decision == RiskDecision.APPROVE

    assert trade_plan.position_size > 0.0

    assert trade_plan.risk_reward_ratio >= 2.0


if __name__ == "__main__":
    test_risk_manager()