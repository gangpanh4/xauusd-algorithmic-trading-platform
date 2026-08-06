"""Deterministic offline drills for restart intent reconciliation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

from core.mt5_execution.models import (
    ActiveOrderInfo,
    ExecutionDealInfo,
    HistoricalOrderInfo,
    OrderRequest,
    OrderSide,
)

from .execution_intent_reconciliation import (
    ExecutionIntentReconciliationDisposition,
    ExecutionIntentReconciliationError,
    reconcile_execution_intent,
)
from .execution_intent_store import (
    ExecutionIntentStatus,
    PersistedExecutionIntent,
    build_execution_intent,
)

_DEFAULT_MAGIC_NUMBER: Final = 20260722
_DEFAULT_TICKET: Final = 910001
_DEFAULT_DEAL_TICKET: Final = 920001


@dataclass(frozen=True, slots=True)
class RestartReconciliationDrillCase:
    """One synthetic broker-evidence restart scenario."""

    name: str
    intent: PersistedExecutionIntent
    active_orders: tuple[ActiveOrderInfo, ...] = ()
    historical_orders: tuple[HistoricalOrderInfo, ...] = ()
    execution_deals: tuple[ExecutionDealInfo, ...] = ()
    expected_disposition: str = ""
    expected_status: str = ""
    expect_fail_closed: bool = False


@dataclass(frozen=True, slots=True)
class RestartReconciliationDrillResult:
    """Observed outcome for one offline restart scenario."""

    name: str
    passed: bool
    fail_closed: bool
    disposition: str
    status: str
    reason: str
    order_ticket: int | None
    deal_tickets: tuple[int, ...]
    automatic_resubmission_attempted: bool = False
    trade_executed: bool = False
    live_execution_enabled: bool = False


@dataclass(frozen=True, slots=True)
class RestartReconciliationDrillSummary:
    """Aggregate evidence for a complete deterministic drill suite."""

    generated_at: datetime
    total_cases: int
    passed_cases: int
    failed_cases: int
    fail_closed_cases: int
    automatic_resubmission_attempted: bool
    trade_executed: bool
    live_execution_enabled: bool
    validation_passed: bool
    results: tuple[RestartReconciliationDrillResult, ...]

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["generated_at"] = self.generated_at.astimezone(UTC).isoformat()
        return payload


def run_restart_reconciliation_drills(
    cases: tuple[RestartReconciliationDrillCase, ...],
    *,
    as_of: datetime,
    generated_at: datetime | None = None,
) -> RestartReconciliationDrillSummary:
    """Run pure simulated reconciliation without connecting to MT5."""

    cutoff = _aware_utc(as_of, "as_of")
    observed: list[RestartReconciliationDrillResult] = []

    for case in cases:
        try:
            result = reconcile_execution_intent(
                intent=case.intent,
                active_orders=case.active_orders,
                historical_orders=case.historical_orders,
                execution_deals=case.execution_deals,
                open_positions=(),
                as_of=cutoff,
            )
        except ExecutionIntentReconciliationError as exc:
            passed = case.expect_fail_closed
            observed.append(
                RestartReconciliationDrillResult(
                    name=case.name,
                    passed=passed,
                    fail_closed=True,
                    disposition="FAILED_CLOSED",
                    status=case.intent.status.value,
                    reason=str(exc),
                    order_ticket=case.intent.ticket,
                    deal_tickets=(),
                )
            )
            continue

        disposition = result.disposition.value
        status = result.intent.status.value
        passed = (
            not case.expect_fail_closed
            and disposition == case.expected_disposition
            and status == case.expected_status
        )
        observed.append(
            RestartReconciliationDrillResult(
                name=case.name,
                passed=passed,
                fail_closed=False,
                disposition=disposition,
                status=status,
                reason=result.reason,
                order_ticket=result.matching_order_ticket,
                deal_tickets=result.matching_deal_tickets,
            )
        )

    results = tuple(observed)
    passed_cases = sum(item.passed for item in results)
    unsafe = any(
        item.automatic_resubmission_attempted
        or item.trade_executed
        or item.live_execution_enabled
        for item in results
    )
    return RestartReconciliationDrillSummary(
        generated_at=(
            datetime.now(UTC)
            if generated_at is None
            else _aware_utc(generated_at, "generated_at")
        ),
        total_cases=len(results),
        passed_cases=passed_cases,
        failed_cases=len(results) - passed_cases,
        fail_closed_cases=sum(item.fail_closed for item in results),
        automatic_resubmission_attempted=False,
        trade_executed=False,
        live_execution_enabled=False,
        validation_passed=(passed_cases == len(results) and not unsafe),
        results=results,
    )


def build_default_restart_reconciliation_drills(
    *,
    observed_at: datetime,
) -> tuple[RestartReconciliationDrillCase, ...]:
    """Build the accepted synthetic restart matrix."""

    timestamp = _aware_utc(observed_at, "observed_at")
    intent = _build_intent(timestamp)
    active = _active_order(intent, timestamp)
    historical_filled = _historical_order(
        intent,
        timestamp,
        state=4,
    )
    historical_cancelled = _historical_order(
        intent,
        timestamp,
        state=2,
    )
    historical_rejected = _historical_order(
        intent,
        timestamp,
        state=5,
    )
    deal = _execution_deal(intent, timestamp)

    return (
        RestartReconciliationDrillCase(
            name="unresolved_no_evidence",
            intent=intent,
            expected_disposition=(
                ExecutionIntentReconciliationDisposition
                .UNRESOLVED_NO_EVIDENCE.value
            ),
            expected_status=ExecutionIntentStatus.PREPARED.value,
        ),
        RestartReconciliationDrillCase(
            name="matching_active_order",
            intent=intent,
            active_orders=(active,),
            expected_disposition=(
                ExecutionIntentReconciliationDisposition
                .ACTIVE_ORDER_CONFIRMED.value
            ),
            expected_status=ExecutionIntentStatus.PENDING.value,
        ),
        RestartReconciliationDrillCase(
            name="matching_full_fill",
            intent=intent,
            historical_orders=(historical_filled,),
            execution_deals=(deal,),
            expected_disposition=(
                ExecutionIntentReconciliationDisposition
                .FILLED_CONFIRMED.value
            ),
            expected_status=ExecutionIntentStatus.FILLED.value,
        ),
        RestartReconciliationDrillCase(
            name="matching_cancelled_order",
            intent=intent,
            historical_orders=(historical_cancelled,),
            expected_disposition=(
                ExecutionIntentReconciliationDisposition
                .CANCELLED_CONFIRMED.value
            ),
            expected_status=ExecutionIntentStatus.CANCELLED.value,
        ),
        RestartReconciliationDrillCase(
            name="matching_rejected_order",
            intent=intent,
            historical_orders=(historical_rejected,),
            expected_disposition=(
                ExecutionIntentReconciliationDisposition
                .REJECTED_CONFIRMED.value
            ),
            expected_status=ExecutionIntentStatus.REJECTED.value,
        ),
        RestartReconciliationDrillCase(
            name="filled_history_without_deal",
            intent=intent,
            historical_orders=(historical_filled,),
            expect_fail_closed=True,
        ),
        RestartReconciliationDrillCase(
            name="conflicting_order_tickets",
            intent=intent,
            active_orders=(active,),
            historical_orders=(
                replace(
                    historical_filled,
                    ticket=_DEFAULT_TICKET + 1,
                ),
            ),
            expect_fail_closed=True,
        ),
        RestartReconciliationDrillCase(
            name="wrong_broker_comment_is_ignored",
            intent=intent,
            active_orders=(
                replace(active, comment="foreign-order"),
            ),
            expected_disposition=(
                ExecutionIntentReconciliationDisposition
                .UNRESOLVED_NO_EVIDENCE.value
            ),
            expected_status=ExecutionIntentStatus.PREPARED.value,
        ),
    )


def export_restart_reconciliation_drill_summary(
    path: str | Path,
    summary: RestartReconciliationDrillSummary,
) -> Path:
    """Export deterministic drill evidence as JSON."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(summary.to_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def _build_intent(timestamp: datetime) -> PersistedExecutionIntent:
    return build_execution_intent(
        observation_timestamp=timestamp,
        created_at=timestamp,
        magic_number=_DEFAULT_MAGIC_NUMBER,
        request=OrderRequest(
            symbol="XAUUSD",
            side=OrderSide.BUY,
            volume=0.01,
            entry_price=2400.0,
            stop_loss=2390.0,
            take_profit=2420.0,
        ),
    )


def _active_order(
    intent: PersistedExecutionIntent,
    timestamp: datetime,
) -> ActiveOrderInfo:
    return ActiveOrderInfo(
        ticket=_DEFAULT_TICKET,
        symbol=intent.symbol,
        side=OrderSide.BUY,
        volume_initial=intent.volume,
        volume_current=intent.volume,
        price_open=intent.entry_price,
        stop_loss=intent.stop_loss,
        take_profit=intent.take_profit,
        magic_number=intent.magic_number,
        comment=intent.broker_comment,
        created_at=timestamp + timedelta(seconds=1),
    )


def _historical_order(
    intent: PersistedExecutionIntent,
    timestamp: datetime,
    *,
    state: int,
) -> HistoricalOrderInfo:
    return HistoricalOrderInfo(
        ticket=_DEFAULT_TICKET,
        symbol=intent.symbol,
        side=OrderSide.BUY,
        volume_initial=intent.volume,
        volume_current=0.0,
        price_open=intent.entry_price,
        stop_loss=intent.stop_loss,
        take_profit=intent.take_profit,
        magic_number=intent.magic_number,
        comment=intent.broker_comment,
        created_at=timestamp + timedelta(seconds=1),
        completed_at=timestamp + timedelta(seconds=2),
        state=state,
    )


def _execution_deal(
    intent: PersistedExecutionIntent,
    timestamp: datetime,
) -> ExecutionDealInfo:
    return ExecutionDealInfo(
        ticket=_DEFAULT_DEAL_TICKET,
        order_ticket=_DEFAULT_TICKET,
        position_id=930001,
        timestamp=timestamp + timedelta(seconds=2),
        symbol=intent.symbol,
        side=OrderSide.BUY,
        volume=intent.volume,
        price=intent.entry_price,
        entry=0,
        magic_number=intent.magic_number,
        comment=intent.broker_comment,
    )


def _aware_utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)
