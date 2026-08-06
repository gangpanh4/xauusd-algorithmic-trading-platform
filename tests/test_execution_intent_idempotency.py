from __future__ import annotations

from datetime import UTC, datetime

import pytest

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
