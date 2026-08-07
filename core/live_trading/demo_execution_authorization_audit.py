"""Offline rejection audit for the demo-execution authorization gate."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from core.mt5_execution.models import AccountInfo, OrderRequest, OrderSide

from .config import LiveTradingConfig
from .demo_execution_authorization import (
    DemoExecutionAuthorization,
    DemoExecutionAuthorizationError,
    consume_demo_execution_authorization,
    load_demo_execution_authorization,
    validate_demo_execution_authorization,
)


@dataclass(frozen=True, slots=True)
class AuthorizationAuditCase:
    """One deterministic authorization-boundary scenario."""

    name: str
    expect_blocked: bool
    expected_reason_fragment: str | None = None


@dataclass(frozen=True, slots=True)
class AuthorizationAuditResult:
    """Observed result for one authorization-boundary scenario."""

    name: str
    blocked: bool
    passed: bool
    reason: str
    broker_submission_attempted: bool
    broker_submission_count: int
    trade_executed: bool


@dataclass(frozen=True, slots=True)
class AuthorizationAuditSummary:
    """Aggregate evidence for the complete rejection matrix."""

    generated_at: datetime
    total_cases: int
    passed_cases: int
    failed_cases: int
    blocked_cases: int
    broker_submission_count: int
    trade_executed: bool
    live_broker_used: bool
    validation_passed: bool
    results: tuple[AuthorizationAuditResult, ...]

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["generated_at"] = self.generated_at.astimezone(UTC).isoformat()
        return payload


def default_authorization_audit_cases() -> tuple[AuthorizationAuditCase, ...]:
    """Return the accepted fail-closed matrix."""

    return (
        AuthorizationAuditCase("missing_file", True, "does not exist"),
        AuthorizationAuditCase("malformed_json", True, "could not be read"),
        AuthorizationAuditCase("expired", True, "expired"),
        AuthorizationAuditCase("not_active_yet", True, "not active yet"),
        AuthorizationAuditCase("already_consumed", True, "already been consumed"),
        AuthorizationAuditCase(
            "wrong_account_login",
            True,
            "account identity does not match",
        ),
        AuthorizationAuditCase(
            "wrong_server",
            True,
            "account identity does not match",
        ),
        AuthorizationAuditCase(
            "real_account",
            True,
            "restricted to an MT5 demo account",
        ),
        AuthorizationAuditCase(
            "wrong_symbol",
            True,
            "symbol does not match",
        ),
        AuthorizationAuditCase(
            "excess_volume",
            True,
            "exceeds the authorized volume",
        ),
        AuthorizationAuditCase(
            "multiple_submissions",
            True,
            "exactly one submission",
        ),
        AuthorizationAuditCase(
            "one_shot_false",
            True,
            "exactly one submission",
        ),
        AuthorizationAuditCase(
            "wrong_acknowledgement",
            True,
            "acknowledgement is invalid",
        ),
        AuthorizationAuditCase("kill_switch", True, "kill switch"),
        AuthorizationAuditCase(
            "demo_not_approved",
            True,
            "not been explicitly approved",
        ),
        AuthorizationAuditCase(
            "live_execution_disabled",
            True,
            "Live execution is disabled",
        ),
        AuthorizationAuditCase(
            "lifetime_too_long",
            True,
            "lifetime is invalid",
        ),
        AuthorizationAuditCase(
            "consume_failure",
            True,
            "Unable to consume",
        ),
        AuthorizationAuditCase("valid_one_shot", False),
        AuthorizationAuditCase(
            "reuse_after_consumption",
            True,
            "already been consumed",
        ),
    )


def run_demo_execution_authorization_audit(
    directory: str | Path,
    *,
    now: datetime,
    generated_at: datetime | None = None,
) -> AuthorizationAuditSummary:
    """Run all authorization cases without using an MT5 broker connection."""

    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    observed_at = _aware_utc(now, "now")
    results: list[AuthorizationAuditResult] = []

    for case in default_authorization_audit_cases():
        case_dir = root / case.name
        case_dir.mkdir(parents=True, exist_ok=True)
        authorization_path = case_dir / "authorization.json"
        config = _config(authorization_path)
        account = _account()
        request = _request()
        consume: Callable[..., DemoExecutionAuthorization] = (
            consume_demo_execution_authorization
        )

        if case.name == "missing_file":
            pass
        elif case.name == "malformed_json":
            authorization_path.write_text("{", encoding="utf-8")
        else:
            payload = _payload(observed_at)
            if case.name == "expired":
                payload["issued_at"] = (
                    observed_at - timedelta(minutes=10)
                ).isoformat()
                payload["expires_at"] = (
                    observed_at - timedelta(minutes=1)
                ).isoformat()
            elif case.name == "not_active_yet":
                payload["issued_at"] = (
                    observed_at + timedelta(minutes=1)
                ).isoformat()
                payload["expires_at"] = (
                    observed_at + timedelta(minutes=5)
                ).isoformat()
            elif case.name in {"already_consumed", "reuse_after_consumption"}:
                payload["consumed_at"] = (
                    observed_at - timedelta(seconds=1)
                ).isoformat()
                payload["consumed_intent_key"] = "a" * 64
            elif case.name == "wrong_account_login":
                payload["account_login"] = 999999
            elif case.name == "wrong_server":
                payload["account_server"] = "Wrong-Demo"
            elif case.name == "real_account":
                account = replace(account, trade_mode=2)
            elif case.name == "wrong_symbol":
                payload["symbol"] = "EURUSD"
            elif case.name == "excess_volume":
                request = _request(volume=0.02)
            elif case.name == "multiple_submissions":
                payload["maximum_submissions"] = 2
            elif case.name == "one_shot_false":
                payload["one_shot"] = False
            elif case.name == "wrong_acknowledgement":
                payload["acknowledgement"] = "AUTHORIZE"
            elif case.name == "kill_switch":
                config = replace(config, execution_kill_switch_enabled=True)
            elif case.name == "demo_not_approved":
                config = replace(config, demo_execution_approved=False)
            elif case.name == "live_execution_disabled":
                config = replace(config, live_execution_enabled=False)
            elif case.name == "lifetime_too_long":
                payload["issued_at"] = (
                    observed_at - timedelta(minutes=1)
                ).isoformat()
                payload["expires_at"] = (
                    observed_at + timedelta(minutes=30)
                ).isoformat()
            elif case.name == "consume_failure":
                consume = _consume_failure
            authorization_path.write_text(
                json.dumps(payload, sort_keys=True),
                encoding="utf-8",
            )

        submission_count = 0
        blocked = False
        reason = ""

        try:
            authorization = load_demo_execution_authorization(
                authorization_path
            )
            validate_demo_execution_authorization(
                authorization,
                config=config,
                account=account,
                request=request,
                now=observed_at,
            )
            consume(
                authorization_path,
                authorization,
                intent_key="b" * 64,
                consumed_at=observed_at,
            )
            submission_count += 1
        except DemoExecutionAuthorizationError as exc:
            blocked = True
            reason = str(exc)

        reason_ok = (
            case.expected_reason_fragment is None
            or case.expected_reason_fragment.lower() in reason.lower()
        )
        passed = blocked == case.expect_blocked and reason_ok
        results.append(
            AuthorizationAuditResult(
                name=case.name,
                blocked=blocked,
                passed=passed,
                reason=reason,
                broker_submission_attempted=submission_count > 0,
                broker_submission_count=submission_count,
                trade_executed=False,
            )
        )

    immutable_results = tuple(results)
    passed_cases = sum(result.passed for result in immutable_results)
    submission_count = sum(
        result.broker_submission_count for result in immutable_results
    )
    valid_submissions = sum(
        result.broker_submission_count
        for result in immutable_results
        if result.name == "valid_one_shot"
    )
    rejected_submissions = sum(
        result.broker_submission_count
        for result in immutable_results
        if result.name != "valid_one_shot"
    )

    return AuthorizationAuditSummary(
        generated_at=(
            datetime.now(UTC)
            if generated_at is None
            else _aware_utc(generated_at, "generated_at")
        ),
        total_cases=len(immutable_results),
        passed_cases=passed_cases,
        failed_cases=len(immutable_results) - passed_cases,
        blocked_cases=sum(result.blocked for result in immutable_results),
        broker_submission_count=submission_count,
        trade_executed=False,
        live_broker_used=False,
        validation_passed=(
            passed_cases == len(immutable_results)
            and valid_submissions == 1
            and rejected_submissions == 0
        ),
        results=immutable_results,
    )


def export_authorization_audit_summary(
    path: str | Path,
    summary: AuthorizationAuditSummary,
) -> Path:
    """Export audit evidence as deterministic JSON."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(summary.to_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def _config(path: Path) -> LiveTradingConfig:
    return LiveTradingConfig(
        live_execution_enabled=True,
        demo_execution_approved=True,
        execution_kill_switch_enabled=False,
        approved_account_login=123456,
        approved_account_server="MetaQuotes-Demo",
        demo_authorization_path=path,
        demo_authorization_max_lifetime_seconds=900,
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


def _request(*, volume: float = 0.01) -> OrderRequest:
    return OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=volume,
        entry_price=2400.0,
        stop_loss=2390.0,
        take_profit=2420.0,
    )


def _payload(now: datetime) -> dict[str, object]:
    return {
        "schema_version": 1,
        "authorization_id": "rejection-audit",
        "issued_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(minutes=4)).isoformat(),
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


def _consume_failure(*args: object, **kwargs: object) -> DemoExecutionAuthorization:
    raise DemoExecutionAuthorizationError(
        "Unable to consume demo execution authorization durably."
    )


def _aware_utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)
