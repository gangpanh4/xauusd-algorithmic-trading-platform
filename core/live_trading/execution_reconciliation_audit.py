"""Append-only audit evidence for restart execution-intent reconciliation."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .execution_intent_store import PersistedExecutionIntent


class ExecutionReconciliationAuditError(RuntimeError):
    """Raised when reconciliation audit evidence cannot be persisted safely."""


@dataclass(frozen=True, slots=True)
class ExecutionReconciliationAudit:
    """One immutable record of a startup reconciliation attempt."""

    recorded_at: datetime
    intent_key: str
    broker_comment: str
    magic_number: int
    intent_status_before: str
    intent_status_after: str
    reconciliation_disposition: str
    matching_order_ticket: int | None
    matching_deal_tickets: tuple[int, ...]
    active_order_match_count: int
    historical_order_match_count: int
    execution_deal_match_count: int
    open_position_match_count: int
    startup_allowed: bool
    automatic_resubmission_attempted: bool
    live_execution_enabled: bool
    shadow_only: bool
    trade_executed: bool
    failure_reason: str

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["recorded_at"] = _aware_utc(
            self.recorded_at,
            "recorded_at",
        ).isoformat()
        payload["matching_deal_tickets"] = list(self.matching_deal_tickets)
        return payload


def build_execution_reconciliation_audit(
    *,
    intent_before: PersistedExecutionIntent,
    intent_after: PersistedExecutionIntent,
    disposition: str,
    matching_order_ticket: int | None,
    matching_deal_tickets: tuple[int, ...],
    active_order_match_count: int,
    historical_order_match_count: int,
    execution_deal_match_count: int,
    open_position_match_count: int,
    startup_allowed: bool,
    live_execution_enabled: bool,
    failure_reason: str = "",
    recorded_at: datetime | None = None,
) -> ExecutionReconciliationAudit:
    """Build a strict non-authoritative audit row."""

    return ExecutionReconciliationAudit(
        recorded_at=datetime.now(UTC) if recorded_at is None else recorded_at,
        intent_key=intent_before.intent_key,
        broker_comment=intent_before.broker_comment,
        magic_number=intent_before.magic_number,
        intent_status_before=intent_before.status.value,
        intent_status_after=intent_after.status.value,
        reconciliation_disposition=disposition,
        matching_order_ticket=matching_order_ticket,
        matching_deal_tickets=matching_deal_tickets,
        active_order_match_count=_count(
            active_order_match_count,
            "active_order_match_count",
        ),
        historical_order_match_count=_count(
            historical_order_match_count,
            "historical_order_match_count",
        ),
        execution_deal_match_count=_count(
            execution_deal_match_count,
            "execution_deal_match_count",
        ),
        open_position_match_count=_count(
            open_position_match_count,
            "open_position_match_count",
        ),
        startup_allowed=bool(startup_allowed),
        automatic_resubmission_attempted=False,
        live_execution_enabled=bool(live_execution_enabled),
        shadow_only=not bool(live_execution_enabled),
        trade_executed=False,
        failure_reason=str(failure_reason),
    )


def append_execution_reconciliation_audit(
    path: str | Path,
    audit: ExecutionReconciliationAudit,
) -> None:
    """Append and fsync exactly one JSONL audit record."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(
        audit.to_payload(),
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    try:
        with target.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise ExecutionReconciliationAuditError(
            f"Unable to append reconciliation audit evidence: {target}"
        ) from exc


def _aware_utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _count(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value
