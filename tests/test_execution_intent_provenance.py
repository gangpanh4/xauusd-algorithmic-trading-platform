from __future__ import annotations

from datetime import UTC, datetime

from core.live_trading.execution_intent_store import build_execution_intent
from core.mt5_execution.models import OrderRequest, OrderSide


def test_execution_intent_contains_deterministic_broker_provenance() -> None:
    request = OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.01,
        entry_price=4000.0,
        stop_loss=3990.0,
        take_profit=4020.0,
    )

    first = build_execution_intent(
        observation_timestamp=datetime(2026, 8, 6, 10, 0, tzinfo=UTC),
        request=request,
        magic_number=234000,
    )
    second = build_execution_intent(
        observation_timestamp=datetime(2026, 8, 6, 10, 0, tzinfo=UTC),
        request=request,
        magic_number=234000,
    )

    assert first.intent_key == second.intent_key
    assert first.magic_number == 234000
    assert first.broker_comment == f"xau:{first.intent_key[:16]}"
    assert len(first.broker_comment) <= 31
