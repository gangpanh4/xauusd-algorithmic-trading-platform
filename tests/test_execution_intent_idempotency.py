from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

import core.live_trading.engine as live_engine_module
from core.live_trading.config import LiveTradingConfig
from core.live_trading.engine import LiveTradingEngine
from core.live_trading.execution_intent_store import (
    ExecutionIntentStateError,
    ExecutionIntentStatus,
)
from core.mt5_execution.models import OrderRequest, OrderSide


def _request() -> OrderRequest:
    return OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.01,
        entry_price=4000.0,
        stop_loss=3990.0,
        take_profit=4020.0,
    )


def test_engine_blocks_same_intent_after_restart(tmp_path) -> None:
    config = LiveTradingConfig(
        execution_intent_state_path=tmp_path / "intent.json",
    )
    timestamp = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)

    first = LiveTradingEngine(config)
    prepared = first._prepare_execution_intent(
        observation_timestamp=timestamp,
        request=_request(),
    )

    second = LiveTradingEngine(config)
    with pytest.raises(
        ExecutionIntentStateError,
        match="Duplicate execution intent",
    ):
        second._prepare_execution_intent(
            observation_timestamp=timestamp,
            request=_request(),
        )

    assert prepared.status is ExecutionIntentStatus.PREPARED


def test_engine_blocks_new_intent_while_prior_is_unresolved(
    tmp_path,
) -> None:
    config = LiveTradingConfig(
        execution_intent_state_path=tmp_path / "intent.json",
    )
    engine = LiveTradingEngine(config)
    engine._prepare_execution_intent(
        observation_timestamp=datetime(
            2026,
            8,
            6,
            10,
            0,
            tzinfo=UTC,
        ),
        request=_request(),
    )

    with pytest.raises(
        ExecutionIntentStateError,
        match="remains unresolved",
    ):
        engine._prepare_execution_intent(
            observation_timestamp=datetime(
                2026,
                8,
                6,
                10,
                5,
                tzinfo=UTC,
            ),
            request=_request(),
        )


def test_legacy_rejected_ticket_is_migrated_and_blocks_new_intent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    config = LiveTradingConfig(
        execution_intent_state_path=tmp_path / "intent.json",
        execution_reconciliation_audit_path=tmp_path / "audit.jsonl",
    )
    engine = LiveTradingEngine(config)
    prepared = engine._prepare_execution_intent(
        observation_timestamp=datetime(
            2026,
            8,
            6,
            10,
            0,
            tzinfo=UTC,
        ),
        request=_request(),
    )
    engine.execution_intent_store.save(
        replace(
            prepared,
            status=ExecutionIntentStatus.REJECTED,
            ticket=4242,
        )
    )

    monkeypatch.setattr(
        live_engine_module,
        "get_active_orders",
        lambda symbol: (),
    )
    monkeypatch.setattr(
        live_engine_module,
        "get_historical_orders",
        lambda **kwargs: (),
    )
    monkeypatch.setattr(
        live_engine_module,
        "get_execution_deals",
        lambda **kwargs: (),
    )
    monkeypatch.setattr(
        live_engine_module,
        "get_open_positions",
        lambda symbol: (),
    )

    result = engine.reconcile_execution_intent(
        as_of=datetime(2026, 8, 6, 10, 5, tzinfo=UTC)
    )

    assert result is not None
    assert result.intent.status is ExecutionIntentStatus.PENDING
    assert result.intent.unresolved is True
    assert engine.execution_intent_store.load() == result.intent
    assert engine.state.active_order_count == 1

    with pytest.raises(
        ExecutionIntentStateError,
        match="remains unresolved",
    ):
        engine._prepare_execution_intent(
            observation_timestamp=datetime(
                2026,
                8,
                6,
                10,
                5,
                tzinfo=UTC,
            ),
            request=_request(),
        )
