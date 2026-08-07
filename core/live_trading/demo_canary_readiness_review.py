"""Read-only readiness review for a future one-shot MT5 demo canary.

This module never initializes MT5, consumes an authorization document, or
submits an order. It evaluates prospective canary prerequisites only.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from core.mt5_execution.models import OrderRequest

from .config import LiveTradingConfig
from .demo_execution_authorization import (
    DemoExecutionAuthorization,
    DemoExecutionAuthorizationError,
    validate_demo_execution_authorization,
)
from .execution_readiness import (
    ExecutionReadinessInputs,
    assess_execution_readiness,
)


class DemoCanaryReadinessReviewError(RuntimeError):
    """Raised when a readiness review cannot be evaluated safely."""


@dataclass(frozen=True, slots=True)
class DemoCanaryReadinessReview:
    """Immutable review result that never grants broker execution authority."""

    reviewed_at: datetime
    account_login: int
    account_server: str
    symbol: str
    requested_volume: float
    readiness_prerequisites_passed: bool
    authorization_draft_valid: bool
    reconciliation_clear: bool
    active_order_clear: bool
    unresolved_partial_fill_clear: bool
    session_submission_limit_clear: bool
    failure_circuit_breaker_clear: bool
    kill_switch_currently_enabled: bool
    live_execution_currently_enabled: bool
    demo_execution_currently_approved: bool
    review_passed: bool
    canary_execution_authorized: bool
    reasons: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["reviewed_at"] = self.reviewed_at.astimezone(UTC).isoformat()
        payload["reasons"] = list(self.reasons)
        return payload


def review_demo_canary_readiness(
    *,
    config: LiveTradingConfig,
    readiness_inputs: ExecutionReadinessInputs,
    authorization: DemoExecutionAuthorization,
    request: OrderRequest,
    reconciliation_status: str,
    now: datetime,
) -> DemoCanaryReadinessReview:
    """Evaluate a prospective one-shot demo canary without enabling execution."""

    observed_at = _aware_utc(now, "now")
    reasons: list[str] = []

    if config.live_execution_enabled:
        reasons.append(
            "Readiness review requires live execution to remain disabled."
        )
    if config.demo_execution_approved:
        reasons.append(
            "Readiness review requires demo execution approval to remain false."
        )
    if not config.execution_kill_switch_enabled:
        reasons.append(
            "Readiness review requires the execution kill switch to remain enabled."
        )

    if not isinstance(reconciliation_status, str):
        raise TypeError("reconciliation_status must be a string")
    normalized_reconciliation = reconciliation_status.strip().upper()
    reconciliation_clear = normalized_reconciliation in {
        "",
        "NO_PERSISTED_INTENT",
        "RECONCILED_CLEAR",
    }
    if not reconciliation_clear:
        reasons.append(
            "Execution-intent reconciliation is not clear for a canary review."
        )

    # Assess the same readiness contract prospectively while preserving the
    # actual supplied configuration in its safe disabled state.
    prospective_config = replace(
        config,
        live_execution_enabled=True,
        demo_execution_approved=True,
        execution_kill_switch_enabled=False,
    )
    readiness = assess_execution_readiness(
        prospective_config,
        readiness_inputs,
    )
    readiness_prerequisites_passed = readiness.ready
    if not readiness_prerequisites_passed:
        reasons.extend(
            f"Prospective readiness: {reason}" for reason in readiness.reasons
        )

    authorization_draft_valid = True
    try:
        validate_demo_execution_authorization(
            authorization,
            config=prospective_config,
            account=readiness_inputs.account,
            request=request,
            now=observed_at,
        )
    except DemoExecutionAuthorizationError as exc:
        authorization_draft_valid = False
        reasons.append(f"Authorization draft: {exc}")

    active_order_clear = readiness_inputs.active_order_count == 0
    unresolved_partial_fill_clear = (
        readiness_inputs.unresolved_partial_ticket is None
    )
    session_submission_limit_clear = readiness.session_submission_limit_clear
    failure_circuit_breaker_clear = readiness.failure_circuit_breaker_clear

    review_passed = all(
        (
            not config.live_execution_enabled,
            not config.demo_execution_approved,
            config.execution_kill_switch_enabled,
            readiness_prerequisites_passed,
            authorization_draft_valid,
            reconciliation_clear,
            active_order_clear,
            unresolved_partial_fill_clear,
            session_submission_limit_clear,
            failure_circuit_breaker_clear,
        )
    )

    # Deliberately immutable invariant: a review can never authorize execution.
    canary_execution_authorized = False
    if review_passed:
        reasons.append(
            "Review passed, but canary execution remains unauthorized; "
            "a separate explicit launch decision is required."
        )

    return DemoCanaryReadinessReview(
        reviewed_at=observed_at,
        account_login=readiness_inputs.account.login,
        account_server=readiness_inputs.account.server,
        symbol=request.symbol,
        requested_volume=float(request.volume),
        readiness_prerequisites_passed=readiness_prerequisites_passed,
        authorization_draft_valid=authorization_draft_valid,
        reconciliation_clear=reconciliation_clear,
        active_order_clear=active_order_clear,
        unresolved_partial_fill_clear=unresolved_partial_fill_clear,
        session_submission_limit_clear=session_submission_limit_clear,
        failure_circuit_breaker_clear=failure_circuit_breaker_clear,
        kill_switch_currently_enabled=config.execution_kill_switch_enabled,
        live_execution_currently_enabled=config.live_execution_enabled,
        demo_execution_currently_approved=config.demo_execution_approved,
        review_passed=review_passed,
        canary_execution_authorized=canary_execution_authorized,
        reasons=tuple(reasons),
    )


def export_demo_canary_readiness_review(
    path: str | Path,
    review: DemoCanaryReadinessReview,
) -> Path:
    """Export one deterministic JSON readiness-review artifact."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(review.to_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def _aware_utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)
