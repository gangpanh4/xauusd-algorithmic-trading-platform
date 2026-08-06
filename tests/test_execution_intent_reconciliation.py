from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from core.live_trading.execution_intent_reconciliation import (
    ExecutionIntentReconciliationDisposition,
    ExecutionIntentReconciliationError,
    reconcile_execution_intent,
)
from core.live_trading.execution_intent_store import (
    ExecutionIntentStatus,
    build_execution_intent,
)
from core.mt5_execution.models import (
    ActiveOrderInfo,
    ExecutionDealInfo,
    HistoricalOrderInfo,
    OrderRequest,
    OrderSide,
)

NOW = datetime(2026, 8, 7, 1, 0, tzinfo=UTC)


def _intent():
    return build_execution_intent(
        observation_timestamp=NOW,
        created_at=NOW,
        magic_number=20260722,
        request=OrderRequest(
            symbol="XAUUSD",
            side=OrderSide.BUY,
            volume=0.01,
            entry_price=2400.0,
            stop_loss=2390.0,
            take_profit=2420.0,
        ),
    )


def _active(intent, *, ticket=101):
    return ActiveOrderInfo(
        ticket=ticket,
        symbol=intent.symbol,
        side=OrderSide.BUY,
        volume_initial=intent.volume,
        volume_current=intent.volume,
        price_open=intent.entry_price,
        stop_loss=intent.stop_loss,
        take_profit=intent.take_profit,
        magic_number=intent.magic_number,
        comment=intent.broker_comment,
        created_at=NOW + timedelta(seconds=1),
    )


def _historical(intent, *, state=4, ticket=101):
    return HistoricalOrderInfo(
        ticket=ticket,
        symbol=intent.symbol,
        side=OrderSide.BUY,
        volume_initial=intent.volume,
        volume_current=0.0,
        price_open=intent.entry_price,
        stop_loss=intent.stop_loss,
        take_profit=intent.take_profit,
        magic_number=intent.magic_number,
        comment=intent.broker_comment,
        created_at=NOW + timedelta(seconds=1),
        completed_at=NOW + timedelta(seconds=2),
        state=state,
    )


def _deal(intent, *, volume=0.01, ticket=201, order_ticket=101):
    return ExecutionDealInfo(
        ticket=ticket,
        order_ticket=order_ticket,
        position_id=301,
        timestamp=NOW + timedelta(seconds=2),
        symbol=intent.symbol,
        side=OrderSide.BUY,
        volume=volume,
        price=intent.entry_price,
        entry=0,
        magic_number=intent.magic_number,
        comment=intent.broker_comment,
    )


def test_no_evidence_preserves_unresolved_prepared_intent() -> None:
    intent = _intent()
    result = reconcile_execution_intent(
        intent=intent,
        active_orders=(),
        historical_orders=(),
        execution_deals=(),
        open_positions=(),
        as_of=NOW + timedelta(minutes=1),
    )
    assert result.intent == intent
    assert result.disposition is (
        ExecutionIntentReconciliationDisposition.UNRESOLVED_NO_EVIDENCE
    )


def test_matching_active_order_confirms_pending() -> None:
    intent = _intent()
    result = reconcile_execution_intent(
        intent=intent,
        active_orders=(_active(intent),),
        historical_orders=(),
        execution_deals=(),
        open_positions=(),
        as_of=NOW + timedelta(minutes=1),
    )
    assert result.intent.status is ExecutionIntentStatus.PENDING
    assert result.intent.ticket == 101


def test_historical_order_and_deal_confirm_full_fill() -> None:
    intent = _intent()
    result = reconcile_execution_intent(
        intent=intent,
        active_orders=(),
        historical_orders=(_historical(intent),),
        execution_deals=(_deal(intent),),
        open_positions=(),
        as_of=NOW + timedelta(minutes=1),
    )
    assert result.intent.status is ExecutionIntentStatus.FILLED
    assert result.matching_deal_tickets == (201,)


def test_multiple_order_tickets_fail_closed() -> None:
    intent = _intent()
    with pytest.raises(
        ExecutionIntentReconciliationError,
        match="Multiple broker order tickets",
    ):
        reconcile_execution_intent(
            intent=intent,
            active_orders=(_active(intent, ticket=101),),
            historical_orders=(_historical(intent, ticket=102),),
            execution_deals=(),
            open_positions=(),
            as_of=NOW + timedelta(minutes=1),
        )


def test_filled_history_without_deal_fails_closed() -> None:
    intent = _intent()
    with pytest.raises(
        ExecutionIntentReconciliationError,
        match="no matching execution deal",
    ):
        reconcile_execution_intent(
            intent=intent,
            active_orders=(),
            historical_orders=(_historical(intent, state=4),),
            execution_deals=(),
            open_positions=(),
            as_of=NOW + timedelta(minutes=1),
        )


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (2, ExecutionIntentStatus.CANCELLED),
        (5, ExecutionIntentStatus.REJECTED),
        (6, ExecutionIntentStatus.CANCELLED),
    ],
)
def test_terminal_history_without_deal_resolves(
    state: int,
    expected: ExecutionIntentStatus,
) -> None:
    intent = _intent()
    result = reconcile_execution_intent(
        intent=intent,
        active_orders=(),
        historical_orders=(_historical(intent, state=state),),
        execution_deals=(),
        open_positions=(),
        as_of=NOW + timedelta(minutes=1),
    )
    assert result.intent.status is expected


def test_wrong_comment_is_not_identity() -> None:
    intent = _intent()
    wrong = replace(_active(intent), comment="xau:not-this-intent")
    result = reconcile_execution_intent(
        intent=intent,
        active_orders=(wrong,),
        historical_orders=(),
        execution_deals=(),
        open_positions=(),
        as_of=NOW + timedelta(minutes=1),
    )
    assert result.disposition is (
        ExecutionIntentReconciliationDisposition.UNRESOLVED_NO_EVIDENCE
    )
