from __future__ import annotations

from dataclasses import replace

from core.live_trading.config import LiveTradingConfig
from core.live_trading.execution_readiness import (
    ExecutionReadinessInputs,
    assess_execution_readiness,
)
from core.mt5_execution.models import AccountInfo


def _account(*, trade_mode: int = 0) -> AccountInfo:
    return AccountInfo(
        login=123456,
        server="Broker-Demo",
        balance=10_000.0,
        equity=10_000.0,
        margin=0.0,
        free_margin=10_000.0,
        leverage=100,
        currency="USD",
        trade_mode=trade_mode,
    )


def _config() -> LiveTradingConfig:
    return LiveTradingConfig(
        live_execution_enabled=False,
        demo_execution_approved=True,
        execution_kill_switch_enabled=False,
        approved_account_login=123456,
        approved_account_server="Broker-Demo",
        maximum_order_submissions_per_session=1,
        maximum_consecutive_execution_failures=1,
    )


def _inputs() -> ExecutionReadinessInputs:
    return ExecutionReadinessInputs(
        account=_account(),
        positions_synchronized=True,
        active_orders_synchronized=True,
        realized_deals_synchronized=True,
        symbol_specification_loaded=True,
        clock_normalization_validated=True,
        parity_validation_passed=True,
        active_order_count=0,
        unresolved_partial_ticket=None,
        order_submissions_this_session=0,
        consecutive_execution_failures=0,
    )


def test_readiness_only_never_enables_execution() -> None:
    result = assess_execution_readiness(_config(), _inputs())

    assert result.ready is False
    assert result.live_execution_enabled is False
    assert result.demo_execution_approved is True
    assert result.reasons == ("Live execution remains disabled.",)


def test_default_config_fails_closed() -> None:
    result = assess_execution_readiness(
        LiveTradingConfig(),
        _inputs(),
    )

    assert result.ready is False
    assert result.kill_switch_clear is False
    assert "Execution kill switch is enabled." in result.reasons
    assert "Demo execution has not been explicitly approved." in result.reasons
    assert "Connected MT5 account identity is not approved." in result.reasons


def test_non_demo_account_fails_closed() -> None:
    result = assess_execution_readiness(
        _config(),
        replace(_inputs(), account=_account(trade_mode=2)),
    )

    assert result.ready is False
    assert result.account_is_demo is False
    assert "Connected MT5 account is not explicitly demo." in result.reasons


def test_account_identity_mismatch_fails_closed() -> None:
    result = assess_execution_readiness(
        replace(_config(), approved_account_login=999999),
        _inputs(),
    )

    assert result.account_identity_approved is False
    assert "Connected MT5 account identity is not approved." in result.reasons


def test_unsynchronized_broker_state_fails_closed() -> None:
    result = assess_execution_readiness(
        _config(),
        replace(_inputs(), active_orders_synchronized=False),
    )

    assert result.broker_state_synchronized is False
    assert "Broker startup state is not fully synchronized." in result.reasons


def test_active_order_and_partial_fill_fail_closed() -> None:
    result = assess_execution_readiness(
        _config(),
        replace(
            _inputs(),
            active_order_count=1,
            unresolved_partial_ticket=987,
        ),
    )

    assert result.no_active_order is False
    assert result.no_unresolved_partial_fill is False
    assert "An active broker order blocks readiness." in result.reasons
    assert "An unresolved partial fill blocks readiness." in result.reasons


def test_submission_limit_and_failure_breaker_fail_closed() -> None:
    result = assess_execution_readiness(
        _config(),
        replace(
            _inputs(),
            order_submissions_this_session=1,
            consecutive_execution_failures=1,
        ),
    )

    assert result.session_submission_limit_clear is False
    assert result.failure_circuit_breaker_clear is False


def test_parity_requirement_fails_closed() -> None:
    result = assess_execution_readiness(
        _config(),
        replace(_inputs(), parity_validation_passed=False),
    )

    assert result.parity_validation_passed is False
    assert (
        "Live-versus-replay parity validation has not passed."
        in result.reasons
    )
