"""Fail-closed demo-execution readiness assessment.

This module evaluates prerequisites only. It never submits, adapts, checks,
or sends an order and does not grant execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.mt5_execution.models import AccountInfo

from .config import LiveTradingConfig

_MT5_DEMO_TRADE_MODE = 0


@dataclass(frozen=True, slots=True)
class ExecutionReadinessInputs:
    """Authoritative runtime facts used by the readiness assessment."""

    account: AccountInfo
    positions_synchronized: bool
    active_orders_synchronized: bool
    realized_deals_synchronized: bool
    symbol_specification_loaded: bool
    clock_normalization_validated: bool
    parity_validation_passed: bool
    active_order_count: int
    unresolved_partial_ticket: int | None
    order_submissions_this_session: int
    consecutive_execution_failures: int

    def __post_init__(self) -> None:
        for name in (
            "active_order_count",
            "order_submissions_this_session",
            "consecutive_execution_failures",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer")
            if value < 0:
                raise ValueError(f"{name} cannot be negative")


@dataclass(frozen=True, slots=True)
class ExecutionReadinessResult:
    """Immutable diagnostic result; ``ready`` never enables execution."""

    ready: bool
    reasons: tuple[str, ...]
    live_execution_enabled: bool
    demo_execution_approved: bool
    kill_switch_clear: bool
    account_is_demo: bool
    account_identity_approved: bool
    broker_state_synchronized: bool
    parity_validation_passed: bool
    no_active_order: bool
    no_unresolved_partial_fill: bool
    session_submission_limit_clear: bool
    failure_circuit_breaker_clear: bool


def assess_execution_readiness(
    config: LiveTradingConfig,
    inputs: ExecutionReadinessInputs,
) -> ExecutionReadinessResult:
    """Evaluate all demo-readiness prerequisites without execution authority."""

    reasons: list[str] = []

    kill_switch_clear = not config.execution_kill_switch_enabled
    if not kill_switch_clear:
        reasons.append("Execution kill switch is enabled.")

    if not config.demo_execution_approved:
        reasons.append("Demo execution has not been explicitly approved.")

    account_is_demo = inputs.account.trade_mode == _MT5_DEMO_TRADE_MODE
    if not account_is_demo:
        reasons.append("Connected MT5 account is not explicitly demo.")

    login_approved = (
        config.approved_account_login is not None
        and inputs.account.login == config.approved_account_login
    )
    server_approved = (
        isinstance(config.approved_account_server, str)
        and bool(config.approved_account_server.strip())
        and inputs.account.server == config.approved_account_server
    )
    account_identity_approved = login_approved and server_approved
    if not account_identity_approved:
        reasons.append("Connected MT5 account identity is not approved.")

    broker_state_synchronized = all(
        (
            inputs.positions_synchronized,
            inputs.active_orders_synchronized,
            inputs.realized_deals_synchronized,
            inputs.symbol_specification_loaded,
            inputs.clock_normalization_validated,
        )
    )
    if not broker_state_synchronized:
        reasons.append("Broker startup state is not fully synchronized.")

    if not inputs.parity_validation_passed:
        reasons.append("Live-versus-replay parity validation has not passed.")

    no_active_order = inputs.active_order_count == 0
    if not no_active_order:
        reasons.append("An active broker order blocks readiness.")

    no_unresolved_partial_fill = inputs.unresolved_partial_ticket is None
    if not no_unresolved_partial_fill:
        reasons.append("An unresolved partial fill blocks readiness.")

    session_submission_limit_clear = (
        isinstance(config.maximum_order_submissions_per_session, int)
        and not isinstance(config.maximum_order_submissions_per_session, bool)
        and config.maximum_order_submissions_per_session > 0
        and inputs.order_submissions_this_session
        < config.maximum_order_submissions_per_session
    )
    if not session_submission_limit_clear:
        reasons.append("Session order-submission limit is reached or invalid.")

    failure_circuit_breaker_clear = (
        isinstance(config.maximum_consecutive_execution_failures, int)
        and not isinstance(config.maximum_consecutive_execution_failures, bool)
        and config.maximum_consecutive_execution_failures > 0
        and inputs.consecutive_execution_failures
        < config.maximum_consecutive_execution_failures
    )
    if not failure_circuit_breaker_clear:
        reasons.append("Execution failure circuit breaker is open or invalid.")

    prerequisites_ready = not reasons

    # Readiness assessment is diagnostic only. The current milestone deliberately
    # keeps live_execution_enabled false, so ``ready`` remains false until a later
    # separately approved execution-enablement milestone.
    if not config.live_execution_enabled:
        reasons.append("Live execution remains disabled.")

    ready = prerequisites_ready and config.live_execution_enabled

    return ExecutionReadinessResult(
        ready=ready,
        reasons=tuple(reasons),
        live_execution_enabled=config.live_execution_enabled,
        demo_execution_approved=config.demo_execution_approved,
        kill_switch_clear=kill_switch_clear,
        account_is_demo=account_is_demo,
        account_identity_approved=account_identity_approved,
        broker_state_synchronized=broker_state_synchronized,
        parity_validation_passed=inputs.parity_validation_passed,
        no_active_order=no_active_order,
        no_unresolved_partial_fill=no_unresolved_partial_fill,
        session_submission_limit_clear=session_submission_limit_clear,
        failure_circuit_breaker_clear=failure_circuit_breaker_clear,
    )
