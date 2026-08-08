"""Non-executing demo-canary launch planning and final abort control.

This module is deliberately disconnected from MT5Executor. It cannot initialize
MT5, consume an authorization, or submit an order. It binds a successful
readiness review to an immutable preflight fingerprint and fails closed if any
execution-relevant fact changes before a later, separately approved milestone.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from math import isfinite
from typing import Final

from core.mt5_execution.models import OrderRequest

from .demo_canary_readiness_review import DemoCanaryReadinessReview
from .demo_execution_authorization import DemoExecutionAuthorization

_SCHEMA_VERSION: Final = 1
_DEFAULT_MAX_PLAN_AGE_SECONDS: Final = 60


class DemoCanaryLaunchAbort(RuntimeError):
    """Raised when a canary launch plan must fail closed."""


@dataclass(frozen=True, slots=True)
class DemoCanaryPreflightSnapshot:
    """Execution-relevant facts captured immediately before a future canary."""

    captured_at: datetime
    account_login: int
    account_server: str
    account_trade_mode: int
    symbol: str
    requested_volume: float
    authorization_id: str
    authorization_expires_at: datetime
    authorization_consumed: bool
    active_order_count: int
    open_position_count: int
    unresolved_partial_ticket: int | None
    unresolved_execution_intent: bool
    reconciliation_status: str
    order_submissions_this_session: int
    consecutive_execution_failures: int
    live_execution_enabled: bool
    demo_execution_approved: bool
    execution_kill_switch_enabled: bool

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["captured_at"] = _aware_utc(
            self.captured_at,
            "captured_at",
        ).isoformat()
        payload["authorization_expires_at"] = _aware_utc(
            self.authorization_expires_at,
            "authorization_expires_at",
        ).isoformat()
        return payload


@dataclass(frozen=True, slots=True)
class DemoCanaryLaunchPlan:
    """Short-lived non-authoritative binding of one reviewed canary state."""

    schema_version: int
    plan_id: str
    created_at: datetime
    expires_at: datetime
    authorization_id: str
    account_login: int
    account_server: str
    symbol: str
    requested_volume: float
    preflight_fingerprint: str
    execution_authorized: bool

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["created_at"] = _aware_utc(
            self.created_at,
            "created_at",
        ).isoformat()
        payload["expires_at"] = _aware_utc(
            self.expires_at,
            "expires_at",
        ).isoformat()
        return payload


@dataclass(frozen=True, slots=True)
class DemoCanaryAbortDecision:
    """Final non-executing decision immediately before any future broker call."""

    checked_at: datetime
    abort_required: bool
    launch_ready: bool
    execution_authorized: bool
    reasons: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["checked_at"] = _aware_utc(
            self.checked_at,
            "checked_at",
        ).isoformat()
        payload["reasons"] = list(self.reasons)
        return payload


def build_demo_canary_preflight_snapshot(
    *,
    review: DemoCanaryReadinessReview,
    authorization: DemoExecutionAuthorization,
    request: OrderRequest,
    account_trade_mode: int,
    active_order_count: int,
    open_position_count: int,
    unresolved_partial_ticket: int | None,
    unresolved_execution_intent: bool,
    reconciliation_status: str,
    order_submissions_this_session: int,
    consecutive_execution_failures: int,
    live_execution_enabled: bool,
    demo_execution_approved: bool,
    execution_kill_switch_enabled: bool,
    captured_at: datetime,
) -> DemoCanaryPreflightSnapshot:
    """Capture immutable facts without granting or consuming authority."""

    for name, value in (
        ("active_order_count", active_order_count),
        ("open_position_count", open_position_count),
        ("order_submissions_this_session", order_submissions_this_session),
        ("consecutive_execution_failures", consecutive_execution_failures),
    ):
        _non_negative_int(value, name)

    if not review.review_passed:
        raise DemoCanaryLaunchAbort(
            "Canary readiness review has not passed."
        )
    if review.canary_execution_authorized:
        raise DemoCanaryLaunchAbort(
            "Readiness review unexpectedly claims execution authority."
        )
    if authorization.consumed:
        raise DemoCanaryLaunchAbort(
            "Demo authorization has already been consumed."
        )
    if authorization.authorization_id.strip() == "":
        raise DemoCanaryLaunchAbort("Authorization ID is empty.")
    if request.symbol != review.symbol or request.symbol != authorization.symbol:
        raise DemoCanaryLaunchAbort(
            "Reviewed symbol, authorization symbol, and request symbol differ."
        )
    if not isfinite(float(request.volume)) or float(request.volume) <= 0.0:
        raise DemoCanaryLaunchAbort("Requested volume is invalid.")
    if float(request.volume) > authorization.maximum_volume:
        raise DemoCanaryLaunchAbort(
            "Requested volume exceeds authorization."
        )

    return DemoCanaryPreflightSnapshot(
        captured_at=_aware_utc(captured_at, "captured_at"),
        account_login=review.account_login,
        account_server=review.account_server,
        account_trade_mode=account_trade_mode,
        symbol=request.symbol,
        requested_volume=float(request.volume),
        authorization_id=authorization.authorization_id,
        authorization_expires_at=_aware_utc(
            authorization.expires_at,
            "authorization.expires_at",
        ),
        authorization_consumed=authorization.consumed,
        active_order_count=active_order_count,
        open_position_count=open_position_count,
        unresolved_partial_ticket=unresolved_partial_ticket,
        unresolved_execution_intent=unresolved_execution_intent,
        reconciliation_status=reconciliation_status.strip().upper(),
        order_submissions_this_session=order_submissions_this_session,
        consecutive_execution_failures=consecutive_execution_failures,
        live_execution_enabled=live_execution_enabled,
        demo_execution_approved=demo_execution_approved,
        execution_kill_switch_enabled=execution_kill_switch_enabled,
    )


def create_demo_canary_launch_plan(
    snapshot: DemoCanaryPreflightSnapshot,
    *,
    now: datetime,
    max_age_seconds: int = _DEFAULT_MAX_PLAN_AGE_SECONDS,
) -> DemoCanaryLaunchPlan:
    """Create a short-lived non-authoritative plan from a safe preflight state."""

    observed_at = _aware_utc(now, "now")
    _validate_snapshot_safe(snapshot, observed_at)

    if (
        isinstance(max_age_seconds, bool)
        or not isinstance(max_age_seconds, int)
        or max_age_seconds <= 0
        or max_age_seconds > _DEFAULT_MAX_PLAN_AGE_SECONDS
    ):
        raise DemoCanaryLaunchAbort(
            "Canary launch-plan lifetime is invalid."
        )

    fingerprint = fingerprint_demo_canary_preflight(snapshot)
    plan_id = hashlib.sha256(
        (
            fingerprint
            + "|"
            + snapshot.authorization_id
            + "|"
            + observed_at.isoformat()
        ).encode("utf-8")
    ).hexdigest()

    return DemoCanaryLaunchPlan(
        schema_version=_SCHEMA_VERSION,
        plan_id=plan_id,
        created_at=observed_at,
        expires_at=observed_at + timedelta(seconds=max_age_seconds),
        authorization_id=snapshot.authorization_id,
        account_login=snapshot.account_login,
        account_server=snapshot.account_server,
        symbol=snapshot.symbol,
        requested_volume=snapshot.requested_volume,
        preflight_fingerprint=fingerprint,
        execution_authorized=False,
    )


def evaluate_demo_canary_final_abort_control(
    *,
    plan: DemoCanaryLaunchPlan,
    current_snapshot: DemoCanaryPreflightSnapshot,
    now: datetime,
) -> DemoCanaryAbortDecision:
    """Fail closed if any bound preflight fact changed or became unsafe."""

    observed_at = _aware_utc(now, "now")
    reasons: list[str] = []

    if plan.schema_version != _SCHEMA_VERSION:
        reasons.append("Unsupported canary launch-plan schema version.")
    if plan.execution_authorized:
        reasons.append(
            "Launch plan unexpectedly claims execution authority."
        )
    if observed_at > _aware_utc(plan.expires_at, "plan.expires_at"):
        reasons.append("Canary launch plan has expired.")
    if observed_at < _aware_utc(plan.created_at, "plan.created_at"):
        reasons.append("Canary launch plan is not active yet.")

    current_fingerprint = fingerprint_demo_canary_preflight(
        current_snapshot
    )
    if current_fingerprint != plan.preflight_fingerprint:
        reasons.append(
            "Execution-relevant state changed after preflight."
        )

    if plan.authorization_id != current_snapshot.authorization_id:
        reasons.append("Authorization identity changed after preflight.")
    if (
        plan.account_login != current_snapshot.account_login
        or plan.account_server != current_snapshot.account_server
    ):
        reasons.append("Account identity changed after preflight.")
    if plan.symbol != current_snapshot.symbol:
        reasons.append("Symbol changed after preflight.")
    if plan.requested_volume != current_snapshot.requested_volume:
        reasons.append("Requested volume changed after preflight.")

    try:
        _validate_snapshot_safe(current_snapshot, observed_at)
    except DemoCanaryLaunchAbort as exc:
        reasons.append(str(exc))

    abort_required = bool(reasons)
    return DemoCanaryAbortDecision(
        checked_at=observed_at,
        abort_required=abort_required,
        launch_ready=not abort_required,
        # Critical invariant: this module never authorizes broker execution.
        execution_authorized=False,
        reasons=tuple(reasons),
    )


def fingerprint_demo_canary_preflight(
    snapshot: DemoCanaryPreflightSnapshot,
) -> str:
    """Return a deterministic SHA-256 binding for all preflight facts."""

    canonical = json.dumps(
        snapshot.to_payload(),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_snapshot_safe(
    snapshot: DemoCanaryPreflightSnapshot,
    now: datetime,
) -> None:
    if snapshot.account_trade_mode != 0:
        raise DemoCanaryLaunchAbort("Connected account is not demo.")
    if snapshot.authorization_consumed:
        raise DemoCanaryLaunchAbort(
            "Authorization is already consumed."
        )
    if now > snapshot.authorization_expires_at:
        raise DemoCanaryLaunchAbort("Authorization has expired.")
    if snapshot.active_order_count != 0:
        raise DemoCanaryLaunchAbort(
            "Active broker order blocks canary launch."
        )
    if snapshot.open_position_count != 0:
        raise DemoCanaryLaunchAbort(
            "Open broker position blocks canary launch."
        )
    if snapshot.unresolved_partial_ticket is not None:
        raise DemoCanaryLaunchAbort(
            "Unresolved partial fill blocks canary launch."
        )
    if snapshot.unresolved_execution_intent:
        raise DemoCanaryLaunchAbort(
            "Unresolved execution intent blocks canary launch."
        )
    if snapshot.reconciliation_status not in {
        "",
        "NO_PERSISTED_INTENT",
        "NO_INTENT",
        "RECONCILED_CLEAR",
    }:
        raise DemoCanaryLaunchAbort(
            "Execution reconciliation is not clear."
        )
    if snapshot.order_submissions_this_session != 0:
        raise DemoCanaryLaunchAbort(
            "A prior order submission blocks the one-shot canary."
        )
    if snapshot.consecutive_execution_failures != 0:
        raise DemoCanaryLaunchAbort(
            "Execution failure circuit breaker is not clear."
        )

    # This milestone remains non-executing. A plan is only valid while all
    # runtime execution controls are still in their safe disabled state.
    if snapshot.live_execution_enabled:
        raise DemoCanaryLaunchAbort(
            "Live execution must remain disabled during launch planning."
        )
    if snapshot.demo_execution_approved:
        raise DemoCanaryLaunchAbort(
            "Demo execution approval must remain false during launch planning."
        )
    if not snapshot.execution_kill_switch_enabled:
        raise DemoCanaryLaunchAbort(
            "Kill switch must remain enabled during launch planning."
        )


def _non_negative_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} cannot be negative")


def _aware_utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)
