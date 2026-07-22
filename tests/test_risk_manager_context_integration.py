from datetime import UTC, datetime, timedelta

from core.risk_manager.config import RiskManagerConfig
from core.risk_manager.manager import RiskManager
from core.risk_manager.models import RiskDecision
from core.signal_generator.models import SignalStrength, SignalType, TradingSignal


def _signal(timestamp: datetime, direction: SignalType = SignalType.BUY) -> TradingSignal:
    return TradingSignal(
        timestamp=timestamp,
        signal=direction,
        strength=SignalStrength.STRONG,
        confidence=0.90,
        reason="Risk integration test",
    )


def _evaluate(manager: RiskManager, timestamp: datetime, balance: float = 10_000.0):
    return manager.evaluate_signal(
        signal=_signal(timestamp),
        entry_price=3300.0,
        account_balance=balance,
        stop_loss_distance=250.0,
        pip_value=1.0,
    )


def test_evaluation_initializes_state_and_exports_context_metadata():
    manager = RiskManager(RiskManagerConfig())
    timestamp = datetime(2026, 7, 21, 8, 0, tzinfo=UTC)

    plan = _evaluate(manager, timestamp)

    assert plan.decision is RiskDecision.APPROVE
    assert manager.state.initialized is True
    assert manager.state.virtual_balance == 10_000.0
    assert manager.state.daily_start_balance == 10_000.0
    assert manager.state.current_trading_date == timestamp.date()
    assert plan.timestamp == timestamp
    assert plan.metadata["open_position_count"] == 0
    assert plan.metadata["daily_drawdown"] == 0.0


def test_emergency_stop_rejects_an_otherwise_valid_trade():
    manager = RiskManager(RiskManagerConfig())
    timestamp = datetime(2026, 7, 21, 8, 0, tzinfo=UTC)
    manager.synchronize_account_balance(10_000.0, timestamp=timestamp)
    manager.set_emergency_stop()

    plan = _evaluate(manager, timestamp + timedelta(minutes=15))

    assert plan.decision is RiskDecision.REJECT
    assert plan.position_size == 0.0
    assert plan.reason == "Emergency stop is active."


def test_existing_position_rejects_when_multiple_positions_disabled():
    manager = RiskManager(RiskManagerConfig(allow_multiple_positions=False))
    timestamp = datetime(2026, 7, 21, 8, 0, tzinfo=UTC)
    manager.synchronize_account_balance(10_000.0, timestamp=timestamp)
    manager.register_position_opened()

    plan = _evaluate(manager, timestamp + timedelta(minutes=15))

    assert plan.decision is RiskDecision.REJECT
    assert plan.reason == "Multiple positions are disabled."
    assert manager.state.open_position_count == 1


def test_daily_drawdown_limit_rejects_until_next_utc_day():
    manager = RiskManager(
        RiskManagerConfig(
            max_daily_loss=0.03,
            stop_after_daily_loss=True,
        )
    )
    day_one = datetime(2026, 7, 21, 8, 0, tzinfo=UTC)
    manager.synchronize_account_balance(10_000.0, timestamp=day_one)
    manager.register_completed_trade(
        -300.0,
        timestamp=day_one + timedelta(hours=1),
        balance_after=9_700.0,
    )

    rejected = _evaluate(
        manager,
        day_one + timedelta(hours=2),
        balance=9_700.0,
    )

    assert manager.state.daily_loss_limit_hit is True
    assert rejected.decision is RiskDecision.REJECT
    assert rejected.reason == "Daily loss limit has already been reached."

    day_two = day_one + timedelta(days=1)
    approved = _evaluate(manager, day_two, balance=9_700.0)

    assert approved.decision is RiskDecision.APPROVE
    assert manager.state.current_trading_date == day_two.date()
    assert manager.state.daily_loss_limit_hit is False
    assert manager.state.daily_drawdown == 0.0


def test_maximum_open_positions_is_enforced_when_multiple_positions_allowed():
    manager = RiskManager(
        RiskManagerConfig(
            allow_multiple_positions=True,
            maximum_open_positions=2,
        )
    )
    timestamp = datetime(2026, 7, 21, 8, 0, tzinfo=UTC)
    manager.synchronize_account_balance(10_000.0, timestamp=timestamp)
    manager.set_open_position_count(2)

    plan = _evaluate(manager, timestamp + timedelta(minutes=15))

    assert plan.decision is RiskDecision.REJECT
    assert plan.reason == "Maximum open positions reached."


def test_dynamic_virtual_balance_uses_realized_state_balance_for_sizing():
    manager = RiskManager(
        RiskManagerConfig(
            use_virtual_balance=True,
            virtual_balance=10_000.0,
            dynamic_virtual_balance=True,
        )
    )
    timestamp = datetime(2026, 7, 21, 8, 0, tzinfo=UTC)

    first = _evaluate(manager, timestamp, balance=50_000.0)
    assert first.decision is RiskDecision.APPROVE
    assert first.metadata["working_balance"] == 10_000.0

    manager.register_completed_trade(
        1_000.0,
        timestamp=timestamp + timedelta(hours=1),
        balance_after=11_000.0,
    )
    second = _evaluate(
        manager,
        timestamp + timedelta(hours=2),
        balance=50_000.0,
    )

    assert second.decision is RiskDecision.APPROVE
    assert second.metadata["working_balance"] == 11_000.0


def test_approval_does_not_register_an_open_position_before_execution():
    manager = RiskManager(RiskManagerConfig())
    timestamp = datetime(2026, 7, 21, 8, 0, tzinfo=UTC)

    plan = _evaluate(manager, timestamp)

    assert plan.decision is RiskDecision.APPROVE
    assert manager.state.open_position_count == 0


def test_naive_signal_timestamp_fails_closed_without_raising():
    manager = RiskManager(RiskManagerConfig())
    naive = datetime(2026, 7, 21, 8, 0)

    plan = _evaluate(manager, naive)

    assert plan.decision is RiskDecision.REJECT
    assert plan.position_size == 0.0
    assert "timestamp must be timezone-aware" in plan.reason
