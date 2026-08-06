from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from core.live_trading.execution_intent_store import (
    ExecutionIntentStateError,
    ExecutionIntentStatus,
    ExecutionIntentStore,
    apply_execution_result,
    build_execution_intent,
)
from core.mt5_execution.models import (
    OrderRequest,
    OrderResult,
    OrderSide,
    OrderStatus,
)


def _request() -> OrderRequest:
    return OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.01,
        entry_price=4000.0,
        stop_loss=3990.0,
        take_profit=4020.0,
    )


def _intent():
    return build_execution_intent(
        observation_timestamp=datetime(2026, 8, 6, 10, 0, tzinfo=UTC),
        request=_request(),
        created_at=datetime(2026, 8, 6, 10, 0, 1, tzinfo=UTC),
    )


def test_execution_intent_key_is_deterministic() -> None:
    first = _intent()
    second = _intent()
    assert first.intent_key == second.intent_key
    assert first.status is ExecutionIntentStatus.PREPARED
    assert first.unresolved is True


def test_execution_intent_key_changes_with_timestamp() -> None:
    first = _intent()
    second = build_execution_intent(
        observation_timestamp=first.observation_timestamp.replace(minute=5),
        request=_request(),
        created_at=first.created_at,
    )
    assert first.intent_key != second.intent_key


def test_execution_intent_store_round_trip(tmp_path) -> None:
    store = ExecutionIntentStore(tmp_path / "intent.json")
    intent = _intent()
    store.save(intent)
    assert store.load() == intent


def test_execution_intent_store_rejects_corrupt_state(tmp_path) -> None:
    path = tmp_path / "intent.json"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ExecutionIntentStateError, match="not valid JSON"):
        ExecutionIntentStore(path).load()


def test_execution_intent_store_rejects_schema_drift(tmp_path) -> None:
    path = tmp_path / "intent.json"
    path.write_text(
        json.dumps({"version": 1, "unexpected": True}),
        encoding="utf-8",
    )
    with pytest.raises(ExecutionIntentStateError, match="schema mismatch"):
        ExecutionIntentStore(path).load()


@pytest.mark.parametrize(
    ("order_status", "intent_status", "unresolved"),
    (
        (OrderStatus.PENDING, ExecutionIntentStatus.PENDING, True),
        (
            OrderStatus.PARTIALLY_FILLED,
            ExecutionIntentStatus.PARTIALLY_FILLED,
            True,
        ),
        (OrderStatus.FILLED, ExecutionIntentStatus.FILLED, False),
        (OrderStatus.REJECTED, ExecutionIntentStatus.REJECTED, False),
        (OrderStatus.CANCELLED, ExecutionIntentStatus.CANCELLED, False),
    ),
)
def test_execution_result_maps_to_durable_status(
    order_status: OrderStatus,
    intent_status: ExecutionIntentStatus,
    unresolved: bool,
) -> None:
    result = OrderResult(
        timestamp=datetime(2026, 8, 6, 10, 0, 2, tzinfo=UTC),
        status=order_status,
        ticket=123 if order_status is not OrderStatus.REJECTED else None,
        executed_price=4000.0,
        message="test",
    )
    persisted = apply_execution_result(_intent(), result)
    assert persisted.status is intent_status
    assert persisted.unresolved is unresolved


def test_store_save_is_atomic_when_replace_fails(
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "intent.json"
    store = ExecutionIntentStore(path)
    original = _intent()
    store.save(original)

    def fail_replace(source, destination):
        raise OSError("replace failed")

    monkeypatch.setattr(
        "core.live_trading.execution_intent_store.os.replace",
        fail_replace,
    )
    with pytest.raises(ExecutionIntentStateError, match="Unable to persist"):
        store.save(replace(original, status=ExecutionIntentStatus.FILLED))
    assert store.load() == original
