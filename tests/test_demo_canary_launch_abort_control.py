from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from core.live_trading.demo_canary_launch_abort_control import (
    DemoCanaryLaunchAbort,
    build_demo_canary_preflight_snapshot,
    create_demo_canary_launch_plan,
    evaluate_demo_canary_final_abort_control,
    fingerprint_demo_canary_preflight,
)
from core.live_trading.demo_canary_readiness_review import (
    DemoCanaryReadinessReview,
)
from core.live_trading.demo_execution_authorization import (
    DemoExecutionAuthorization,
)
from core.mt5_execution.models import OrderRequest, OrderSide

NOW = datetime(2026, 8, 8, 2, 30, tzinfo=UTC)


def _review() -> DemoCanaryReadinessReview:
    return DemoCanaryReadinessReview(
        reviewed_at=NOW,
        account_login=123456,
        account_server="MetaQuotes-Demo",
        symbol="XAUUSD",
        requested_volume=0.01,
        readiness_prerequisites_passed=True,
        authorization_draft_valid=True,
        reconciliation_clear=True,
        active_order_clear=True,
        unresolved_partial_fill_clear=True,
        session_submission_limit_clear=True,
        failure_circuit_breaker_clear=True,
        kill_switch_currently_enabled=True,
        live_execution_currently_enabled=False,
        demo_execution_currently_approved=False,
        review_passed=True,
        canary_execution_authorized=False,
        reasons=(
            (
                "Review passed, but canary execution remains unauthorized; "
                "a separate explicit launch decision is required."
            ),
        ),
    )


def _authorization() -> DemoExecutionAuthorization:
    return DemoExecutionAuthorization(
        schema_version=1,
        authorization_id="future-canary-001",
        issued_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=4),
        account_login=123456,
        account_server="MetaQuotes-Demo",
        symbol="XAUUSD",
        maximum_volume=0.01,
        maximum_submissions=1,
        demo_only=True,
        one_shot=True,
        acknowledgement="I AUTHORIZE ONE DEMO ORDER",
        consumed_at=None,
        consumed_intent_key=None,
    )


def _request() -> OrderRequest:
    return OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.01,
        entry_price=2400.0,
        stop_loss=2390.0,
        take_profit=2420.0,
    )


def _snapshot(**overrides):
    values = {
        "review": _review(),
        "authorization": _authorization(),
        "request": _request(),
        "account_trade_mode": 0,
        "active_order_count": 0,
        "open_position_count": 0,
        "unresolved_partial_ticket": None,
        "unresolved_execution_intent": False,
        "reconciliation_status": "NO_PERSISTED_INTENT",
        "order_submissions_this_session": 0,
        "consecutive_execution_failures": 0,
        "live_execution_enabled": False,
        "demo_execution_approved": False,
        "execution_kill_switch_enabled": True,
        "captured_at": NOW,
    }
    values.update(overrides)
    return build_demo_canary_preflight_snapshot(**values)


def test_safe_snapshot_builds_non_authoritative_plan() -> None:
    snapshot = _snapshot()
    plan = create_demo_canary_launch_plan(snapshot, now=NOW)

    assert plan.execution_authorized is False
    assert plan.authorization_id == "future-canary-001"
    assert plan.preflight_fingerprint == fingerprint_demo_canary_preflight(
        snapshot
    )


def test_unchanged_state_is_launch_ready_but_not_authorized() -> None:
    snapshot = _snapshot()
    plan = create_demo_canary_launch_plan(snapshot, now=NOW)

    decision = evaluate_demo_canary_final_abort_control(
        plan=plan,
        current_snapshot=snapshot,
        now=NOW + timedelta(seconds=10),
    )

    assert decision.abort_required is False
    assert decision.launch_ready is True
    assert decision.execution_authorized is False


def test_active_submission_state_is_bound_without_granting_authority() -> None:
    snapshot = _snapshot(
        order_submissions_this_session=1,
        consecutive_execution_failures=1,
        live_execution_enabled=True,
        demo_execution_approved=True,
        execution_kill_switch_enabled=False,
    )
    plan = create_demo_canary_launch_plan(snapshot, now=NOW)
    current = replace(
        snapshot,
        captured_at=NOW + timedelta(seconds=10),
    )

    decision = evaluate_demo_canary_final_abort_control(
        plan=plan,
        current_snapshot=current,
        now=NOW + timedelta(seconds=10),
    )

    assert decision.launch_ready is True
    assert decision.execution_authorized is False
    assert fingerprint_demo_canary_preflight(current) == (
        plan.preflight_fingerprint
    )


@pytest.mark.parametrize(
    "reconciliation_status",
    [
        "ALREADY_RESOLVED",
        "FILLED_CONFIRMED",
        "REJECTED_CONFIRMED",
        "CANCELLED_CONFIRMED",
    ],
)
def test_terminal_restart_dispositions_are_clear(
    reconciliation_status: str,
) -> None:
    snapshot = _snapshot(reconciliation_status=reconciliation_status)

    plan = create_demo_canary_launch_plan(snapshot, now=NOW)

    assert plan.execution_authorized is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("active_order_count", 1),
        ("open_position_count", 1),
        ("unresolved_partial_ticket", 77),
        ("unresolved_execution_intent", True),
        ("reconciliation_status", "UNRESOLVED_NO_EVIDENCE"),
        ("order_submissions_this_session", 1),
        ("consecutive_execution_failures", 1),
        ("live_execution_enabled", True),
        ("demo_execution_approved", True),
        ("execution_kill_switch_enabled", False),
    ],
)
def test_unsafe_state_changes_force_abort(field, value) -> None:
    snapshot = _snapshot()
    plan = create_demo_canary_launch_plan(snapshot, now=NOW)
    changed = replace(snapshot, **{field: value})

    decision = evaluate_demo_canary_final_abort_control(
        plan=plan,
        current_snapshot=changed,
        now=NOW + timedelta(seconds=10),
    )

    assert decision.abort_required is True
    assert decision.launch_ready is False
    assert decision.execution_authorized is False


def test_account_identity_change_forces_abort() -> None:
    snapshot = _snapshot()
    plan = create_demo_canary_launch_plan(snapshot, now=NOW)
    changed = replace(snapshot, account_login=999999)

    decision = evaluate_demo_canary_final_abort_control(
        plan=plan,
        current_snapshot=changed,
        now=NOW + timedelta(seconds=10),
    )

    assert decision.abort_required is True
    assert "Account identity changed after preflight." in decision.reasons


def test_authorization_expiry_forces_abort() -> None:
    snapshot = _snapshot()
    plan = create_demo_canary_launch_plan(snapshot, now=NOW)

    decision = evaluate_demo_canary_final_abort_control(
        plan=plan,
        current_snapshot=snapshot,
        now=NOW + timedelta(minutes=5),
    )

    assert decision.abort_required is True
    assert decision.execution_authorized is False


def test_plan_expiry_forces_abort_even_if_snapshot_unchanged() -> None:
    snapshot = _snapshot()
    plan = create_demo_canary_launch_plan(
        snapshot,
        now=NOW,
        max_age_seconds=30,
    )

    decision = evaluate_demo_canary_final_abort_control(
        plan=plan,
        current_snapshot=snapshot,
        now=NOW + timedelta(seconds=31),
    )

    assert decision.abort_required is True
    assert "Canary launch plan has expired." in decision.reasons


def test_plan_rejects_consumed_authorization() -> None:
    consumed = replace(
        _authorization(),
        consumed_at=NOW,
        consumed_intent_key="a" * 64,
    )

    with pytest.raises(
        DemoCanaryLaunchAbort,
        match="already been consumed",
    ):
        _snapshot(authorization=consumed)


def test_preflight_rejects_open_position_before_plan_creation() -> None:
    snapshot = _snapshot(open_position_count=1)

    with pytest.raises(
        DemoCanaryLaunchAbort,
        match="Open broker position",
    ):
        create_demo_canary_launch_plan(snapshot, now=NOW)
