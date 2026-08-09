from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from core.live_trading.config import LiveTradingConfig
from core.live_trading.demo_canary_readiness_review import (
    export_demo_canary_readiness_review,
    review_demo_canary_readiness,
)
from core.live_trading.demo_execution_authorization import (
    DemoExecutionAuthorization,
)
from core.live_trading.execution_readiness import ExecutionReadinessInputs
from core.mt5_execution.models import AccountInfo, OrderRequest, OrderSide

NOW = datetime(2026, 8, 8, 2, 0, tzinfo=UTC)


def _config(tmp_path) -> LiveTradingConfig:
    return LiveTradingConfig(
        live_execution_enabled=False,
        demo_execution_approved=False,
        execution_kill_switch_enabled=True,
        approved_account_login=123456,
        approved_account_server="MetaQuotes-Demo",
        demo_authorization_path=tmp_path / "authorization.json",
        demo_authorization_max_lifetime_seconds=900,
        maximum_order_submissions_per_session=1,
        maximum_consecutive_execution_failures=1,
    )


def _account() -> AccountInfo:
    return AccountInfo(
        login=123456,
        server="MetaQuotes-Demo",
        balance=10_000.0,
        equity=10_000.0,
        margin=0.0,
        free_margin=10_000.0,
        leverage=100,
        currency="USD",
        trade_mode=0,
    )


def _inputs(**overrides) -> ExecutionReadinessInputs:
    values = {
        "account": _account(),
        "positions_synchronized": True,
        "active_orders_synchronized": True,
        "realized_deals_synchronized": True,
        "symbol_specification_loaded": True,
        "clock_normalization_validated": True,
        "parity_validation_passed": True,
        "active_order_count": 0,
        "unresolved_partial_ticket": None,
        "order_submissions_this_session": 0,
        "consecutive_execution_failures": 0,
    }
    values.update(overrides)
    return ExecutionReadinessInputs(**values)


def _authorization(**overrides) -> DemoExecutionAuthorization:
    values = {
        "schema_version": 1,
        "authorization_id": "future-demo-canary",
        "issued_at": NOW - timedelta(minutes=1),
        "expires_at": NOW + timedelta(minutes=4),
        "account_login": 123456,
        "account_server": "MetaQuotes-Demo",
        "symbol": "XAUUSD",
        "maximum_volume": 0.01,
        "maximum_submissions": 1,
        "demo_only": True,
        "one_shot": True,
        "acknowledgement": "I AUTHORIZE ONE DEMO ORDER",
        "consumed_at": None,
        "consumed_intent_key": None,
    }
    values.update(overrides)
    return DemoExecutionAuthorization(**values)


def _request() -> OrderRequest:
    return OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.01,
        entry_price=2400.0,
        stop_loss=2390.0,
        take_profit=2420.0,
    )


def test_review_passes_but_never_authorizes_execution(tmp_path) -> None:
    review = review_demo_canary_readiness(
        config=_config(tmp_path),
        readiness_inputs=_inputs(),
        authorization=_authorization(),
        request=_request(),
        reconciliation_status="NO_PERSISTED_INTENT",
        now=NOW,
    )

    assert review.review_passed is True
    assert review.readiness_prerequisites_passed is True
    assert review.authorization_draft_valid is True
    assert review.reconciliation_clear is True
    assert review.live_execution_currently_enabled is False
    assert review.demo_execution_currently_approved is False
    assert review.kill_switch_currently_enabled is True
    assert review.canary_execution_authorized is False


def test_active_submission_review_uses_actual_controls_without_authorizing(
    tmp_path,
) -> None:
    config = replace(
        _config(tmp_path),
        live_execution_enabled=True,
        demo_execution_approved=True,
        execution_kill_switch_enabled=False,
    )

    review = review_demo_canary_readiness(
        config=config,
        readiness_inputs=_inputs(),
        authorization=_authorization(),
        request=_request(),
        reconciliation_status="NO_INTENT",
        now=NOW,
    )

    assert review.review_passed is True
    assert review.live_execution_currently_enabled is True
    assert review.demo_execution_currently_approved is True
    assert review.kill_switch_currently_enabled is False
    assert review.canary_execution_authorized is False


def test_review_fails_with_active_order(tmp_path) -> None:
    review = review_demo_canary_readiness(
        config=_config(tmp_path),
        readiness_inputs=_inputs(active_order_count=1),
        authorization=_authorization(),
        request=_request(),
        reconciliation_status="NO_PERSISTED_INTENT",
        now=NOW,
    )

    assert review.review_passed is False
    assert review.active_order_clear is False
    assert review.canary_execution_authorized is False


def test_review_fails_with_invalid_authorization_draft(tmp_path) -> None:
    review = review_demo_canary_readiness(
        config=_config(tmp_path),
        readiness_inputs=_inputs(),
        authorization=_authorization(maximum_volume=0.001),
        request=_request(),
        reconciliation_status="NO_PERSISTED_INTENT",
        now=NOW,
    )

    assert review.review_passed is False
    assert review.authorization_draft_valid is False
    assert review.canary_execution_authorized is False


def test_review_fails_when_reconciliation_is_unresolved(tmp_path) -> None:
    review = review_demo_canary_readiness(
        config=_config(tmp_path),
        readiness_inputs=_inputs(),
        authorization=_authorization(),
        request=_request(),
        reconciliation_status="UNRESOLVED_NO_EVIDENCE",
        now=NOW,
    )

    assert review.review_passed is False
    assert review.reconciliation_clear is False
    assert review.canary_execution_authorized is False


@pytest.mark.parametrize(
    "reconciliation_status",
    [
        "NO_INTENT",
        "ALREADY_RESOLVED",
        "FILLED_CONFIRMED",
        "REJECTED_CONFIRMED",
        "CANCELLED_CONFIRMED",
    ],
)
def test_review_accepts_clear_engine_restart_dispositions(
    tmp_path,
    reconciliation_status: str,
) -> None:
    review = review_demo_canary_readiness(
        config=_config(tmp_path),
        readiness_inputs=_inputs(),
        authorization=_authorization(),
        request=_request(),
        reconciliation_status=reconciliation_status,
        now=NOW,
    )

    assert review.reconciliation_clear is True
    assert review.review_passed is True


def test_review_export_is_explicitly_non_authoritative(tmp_path) -> None:
    review = review_demo_canary_readiness(
        config=_config(tmp_path),
        readiness_inputs=_inputs(),
        authorization=_authorization(),
        request=_request(),
        reconciliation_status="NO_PERSISTED_INTENT",
        now=NOW,
    )
    output = export_demo_canary_readiness_review(
        tmp_path / "review.json",
        review,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["review_passed"] is True
    assert payload["canary_execution_authorized"] is False
    assert payload["live_execution_currently_enabled"] is False
    assert payload["demo_execution_currently_approved"] is False
    assert payload["kill_switch_currently_enabled"] is True
