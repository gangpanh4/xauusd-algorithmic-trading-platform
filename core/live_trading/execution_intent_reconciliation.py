"""Fail-closed restart reconciliation for persisted execution intents."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from math import isclose

from core.mt5_execution.models import (
    ActiveOrderInfo,
    ExecutionDealInfo,
    HistoricalOrderInfo,
    PositionInfo,
)

from .execution_intent_store import (
    ExecutionIntentStatus,
    PersistedExecutionIntent,
)

_ORDER_STATE_CANCELED = 2
_ORDER_STATE_FILLED = 4
_ORDER_STATE_REJECTED = 5
_ORDER_STATE_EXPIRED = 6

_VOLUME_TOLERANCE = 1e-9
_PRE_OBSERVATION_TOLERANCE = timedelta(minutes=5)


class ExecutionIntentReconciliationError(RuntimeError):
    """Raised when broker evidence cannot be reconciled unambiguously."""


class ExecutionIntentReconciliationDisposition(Enum):
    """Outcome of one pure reconciliation pass."""

    ALREADY_RESOLVED = "ALREADY_RESOLVED"
    UNRESOLVED_NO_EVIDENCE = "UNRESOLVED_NO_EVIDENCE"
    ACTIVE_ORDER_CONFIRMED = "ACTIVE_ORDER_CONFIRMED"
    PARTIAL_FILL_CONFIRMED = "PARTIAL_FILL_CONFIRMED"
    FILLED_CONFIRMED = "FILLED_CONFIRMED"
    REJECTED_CONFIRMED = "REJECTED_CONFIRMED"
    CANCELLED_CONFIRMED = "CANCELLED_CONFIRMED"


@dataclass(frozen=True, slots=True)
class ExecutionIntentReconciliationResult:
    """Validated result of comparing one intent with broker evidence."""

    intent: PersistedExecutionIntent
    disposition: ExecutionIntentReconciliationDisposition
    reason: str
    matching_order_ticket: int | None = None
    matching_deal_tickets: tuple[int, ...] = ()


def reconcile_execution_intent(
    *,
    intent: PersistedExecutionIntent,
    active_orders: Sequence[ActiveOrderInfo],
    historical_orders: Sequence[HistoricalOrderInfo],
    execution_deals: Sequence[ExecutionDealInfo],
    open_positions: Sequence[PositionInfo],
    as_of: datetime,
) -> ExecutionIntentReconciliationResult:
    """Reconcile an intent without submitting, modifying, or cancelling orders."""

    cutoff = _aware_utc(as_of, "as_of")
    legacy_ambiguous_rejection = (
        intent.status is ExecutionIntentStatus.REJECTED
        and intent.ticket is not None
    )
    if not intent.unresolved:
        if not legacy_ambiguous_rejection:
            return ExecutionIntentReconciliationResult(
                intent=intent,
                disposition=(
                    ExecutionIntentReconciliationDisposition.ALREADY_RESOLVED
                ),
                reason="Persisted execution intent is already terminal.",
                matching_order_ticket=intent.ticket,
            )

        # Schema-v2 records written before ambiguous acknowledgement handling
        # may contain REJECTED plus a broker order ticket after a fill-like
        # retcode. The durable record does not retain enough acknowledgement
        # detail to prove that no mutation occurred, so it must be reconciled.
        intent = replace(intent, status=ExecutionIntentStatus.PENDING)

    active_matches = tuple(
        order
        for order in active_orders
        if _matches_order(intent, order, cutoff)
    )
    history_matches = tuple(
        order
        for order in historical_orders
        if _matches_order(intent, order, cutoff)
    )
    deal_matches = tuple(
        deal
        for deal in execution_deals
        if _matches_deal(intent, deal, cutoff)
    )

    _reject_multiple_order_tickets(
        intent=intent,
        active_matches=active_matches,
        history_matches=history_matches,
        deal_matches=deal_matches,
    )

    if active_matches:
        if len(active_matches) != 1:
            raise ExecutionIntentReconciliationError(
                "Multiple active broker orders match one execution intent."
            )
        active = active_matches[0]
        if any(
            order.ticket != active.ticket for order in history_matches
        ) or any(
            deal.order_ticket != active.ticket for deal in deal_matches
        ):
            raise ExecutionIntentReconciliationError(
                "Active-order evidence conflicts with terminal broker evidence."
            )
        return ExecutionIntentReconciliationResult(
            intent=_with_status(
                intent,
                status=ExecutionIntentStatus.PENDING,
                ticket=active.ticket,
                updated_at=active.created_at,
            ),
            disposition=(
                ExecutionIntentReconciliationDisposition.ACTIVE_ORDER_CONFIRMED
            ),
            reason="Matching active broker order remains unresolved.",
            matching_order_ticket=active.ticket,
        )

    if not history_matches and not deal_matches:
        reason = (
            "Legacy rejected execution intent contains a broker ticket but no "
            "authoritative matching evidence; automatic resubmission remains "
            "blocked."
            if legacy_ambiguous_rejection
            else (
                "No authoritative broker evidence matched the persisted intent; "
                "automatic resubmission remains blocked."
            )
        )
        return ExecutionIntentReconciliationResult(
            intent=intent,
            disposition=(
                ExecutionIntentReconciliationDisposition.UNRESOLVED_NO_EVIDENCE
            ),
            reason=reason,
            matching_order_ticket=intent.ticket,
        )

    if deal_matches and not history_matches:
        raise ExecutionIntentReconciliationError(
            "Matching execution deals exist without a matching historical order."
        )
    if len(history_matches) != 1:
        raise ExecutionIntentReconciliationError(
            "Historical broker evidence is ambiguous."
        )

    historical = history_matches[0]
    related_deals = tuple(
        deal
        for deal in deal_matches
        if deal.order_ticket == historical.ticket
    )
    if len(related_deals) != len(deal_matches):
        raise ExecutionIntentReconciliationError(
            "Execution deals reference conflicting broker order tickets."
        )

    if related_deals:
        executed_volume = sum(deal.volume for deal in related_deals)
        if executed_volume > intent.volume + _VOLUME_TOLERANCE:
            raise ExecutionIntentReconciliationError(
                "Broker execution volume exceeds the persisted requested volume."
            )
        _validate_position_corroboration(
            intent=intent,
            executed_volume=executed_volume,
            open_positions=open_positions,
        )
        latest = max(deal.timestamp for deal in related_deals)
        deal_tickets = tuple(sorted(deal.ticket for deal in related_deals))
        if isclose(
            executed_volume,
            intent.volume,
            rel_tol=0.0,
            abs_tol=_VOLUME_TOLERANCE,
        ):
            return ExecutionIntentReconciliationResult(
                intent=_with_status(
                    intent,
                    status=ExecutionIntentStatus.FILLED,
                    ticket=historical.ticket,
                    updated_at=latest,
                ),
                disposition=(
                    ExecutionIntentReconciliationDisposition.FILLED_CONFIRMED
                ),
                reason="Historical order and execution deals confirm a full fill.",
                matching_order_ticket=historical.ticket,
                matching_deal_tickets=deal_tickets,
            )
        if executed_volume > 0.0:
            return ExecutionIntentReconciliationResult(
                intent=_with_status(
                    intent,
                    status=ExecutionIntentStatus.PARTIALLY_FILLED,
                    ticket=historical.ticket,
                    updated_at=latest,
                ),
                disposition=(
                    ExecutionIntentReconciliationDisposition.PARTIAL_FILL_CONFIRMED
                ),
                reason=(
                    "Execution deals confirm a partial fill; unresolved state "
                    "remains fail-closed."
                ),
                matching_order_ticket=historical.ticket,
                matching_deal_tickets=deal_tickets,
            )

    if historical.state == _ORDER_STATE_REJECTED:
        status = ExecutionIntentStatus.REJECTED
        disposition = (
            ExecutionIntentReconciliationDisposition.REJECTED_CONFIRMED
        )
        reason = "Matching historical broker order was rejected."
    elif historical.state in {
        _ORDER_STATE_CANCELED,
        _ORDER_STATE_EXPIRED,
    }:
        status = ExecutionIntentStatus.CANCELLED
        disposition = (
            ExecutionIntentReconciliationDisposition.CANCELLED_CONFIRMED
        )
        reason = "Matching historical broker order was cancelled or expired."
    elif historical.state == _ORDER_STATE_FILLED:
        raise ExecutionIntentReconciliationError(
            "Historical order reports FILLED but no matching execution deal exists."
        )
    else:
        raise ExecutionIntentReconciliationError(
            "Historical broker order state is not terminal or recognized."
        )

    return ExecutionIntentReconciliationResult(
        intent=_with_status(
            intent,
            status=status,
            ticket=historical.ticket,
            updated_at=historical.completed_at,
        ),
        disposition=disposition,
        reason=reason,
        matching_order_ticket=historical.ticket,
    )


def _matches_order(
    intent: PersistedExecutionIntent,
    order: ActiveOrderInfo | HistoricalOrderInfo,
    as_of: datetime,
) -> bool:
    created_at = _aware_utc(order.created_at, "order.created_at")
    earliest = (
        intent.observation_timestamp.astimezone(UTC)
        - _PRE_OBSERVATION_TOLERANCE
    )
    return (
        order.symbol == intent.symbol
        and order.side.value == intent.side
        and order.magic_number == intent.magic_number
        and order.comment == intent.broker_comment
        and (intent.ticket is None or order.ticket == intent.ticket)
        and isclose(
            order.volume_initial,
            intent.volume,
            rel_tol=0.0,
            abs_tol=_VOLUME_TOLERANCE,
        )
        and earliest <= created_at <= as_of
    )


def _matches_deal(
    intent: PersistedExecutionIntent,
    deal: ExecutionDealInfo,
    as_of: datetime,
) -> bool:
    timestamp = _aware_utc(deal.timestamp, "deal.timestamp")
    earliest = (
        intent.observation_timestamp.astimezone(UTC)
        - _PRE_OBSERVATION_TOLERANCE
    )
    return (
        deal.symbol == intent.symbol
        and deal.side.value == intent.side
        and deal.magic_number == intent.magic_number
        and deal.comment == intent.broker_comment
        and (intent.ticket is None or deal.order_ticket == intent.ticket)
        and earliest <= timestamp <= as_of
    )


def _reject_multiple_order_tickets(
    *,
    intent: PersistedExecutionIntent,
    active_matches: Sequence[ActiveOrderInfo],
    history_matches: Sequence[HistoricalOrderInfo],
    deal_matches: Sequence[ExecutionDealInfo],
) -> None:
    tickets = {order.ticket for order in active_matches}
    tickets.update(order.ticket for order in history_matches)
    tickets.update(deal.order_ticket for deal in deal_matches)
    if intent.ticket is not None and any(
        ticket != intent.ticket for ticket in tickets
    ):
        raise ExecutionIntentReconciliationError(
            "Broker evidence conflicts with the persisted execution ticket."
        )
    if len(tickets) > 1:
        raise ExecutionIntentReconciliationError(
            "Multiple broker order tickets match one persisted intent."
        )


def _validate_position_corroboration(
    *,
    intent: PersistedExecutionIntent,
    executed_volume: float,
    open_positions: Sequence[PositionInfo],
) -> None:
    matching_volume = sum(
        position.volume
        for position in open_positions
        if (
            position.symbol == intent.symbol
            and position.side.value == intent.side
        )
    )
    if matching_volume > intent.volume + _VOLUME_TOLERANCE:
        raise ExecutionIntentReconciliationError(
            "Open-position volume exceeds the persisted requested volume."
        )
    if (
        matching_volume > 0.0
        and matching_volume + _VOLUME_TOLERANCE < executed_volume
    ):
        raise ExecutionIntentReconciliationError(
            "Open-position volume contradicts matching execution-deal volume."
        )


def _with_status(
    intent: PersistedExecutionIntent,
    *,
    status: ExecutionIntentStatus,
    ticket: int,
    updated_at: datetime,
) -> PersistedExecutionIntent:
    normalized_updated = _aware_utc(updated_at, "updated_at")
    normalized_updated = max(normalized_updated, intent.created_at.astimezone(UTC))
    return replace(
        intent,
        status=status,
        ticket=ticket,
        updated_at=normalized_updated,
    )


def _aware_utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)
