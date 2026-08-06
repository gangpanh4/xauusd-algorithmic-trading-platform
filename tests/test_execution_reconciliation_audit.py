from __future__ import annotations

import json
from datetime import UTC, datetime

from core.live_trading.execution_intent_store import build_execution_intent
from core.live_trading.execution_reconciliation_audit import (
    append_execution_reconciliation_audit,
    build_execution_reconciliation_audit,
)
from core.mt5_execution.models import OrderRequest, OrderSide


def test_append_audit_is_non_authoritative_and_safe(tmp_path) -> None:
    now = datetime(2026, 8, 7, 2, 0, tzinfo=UTC)
    intent = build_execution_intent(
        observation_timestamp=now,
        created_at=now,
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
    audit = build_execution_reconciliation_audit(
        intent_before=intent,
        intent_after=intent,
        disposition="UNRESOLVED_NO_EVIDENCE",
        matching_order_ticket=None,
        matching_deal_tickets=(),
        active_order_match_count=0,
        historical_order_match_count=0,
        execution_deal_match_count=0,
        open_position_match_count=0,
        startup_allowed=False,
        live_execution_enabled=False,
        recorded_at=now,
    )
    path = tmp_path / "audit.jsonl"
    append_execution_reconciliation_audit(path, audit)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["automatic_resubmission_attempted"] is False
    assert payload["trade_executed"] is False
    assert payload["shadow_only"] is True
