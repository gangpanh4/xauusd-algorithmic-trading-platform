from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import core.live_trading.engine as live_engine_module
from core.live_trading.config import LiveTradingConfig
from core.live_trading.engine import LiveTradingEngine
from core.mt5_execution.models import OrderResult, OrderStatus
from core.regime_detector.models import MarketBar
from core.risk_manager.models import RiskDecision


def _bar() -> MarketBar:
    return MarketBar(
        timestamp=datetime.now(UTC),
        open=4000.0,
        high=4005.0,
        low=3998.0,
        close=4003.0,
        volume=1000,
    )


def _approved():
    return SimpleNamespace(
        signal=SimpleNamespace(direction="BUY"),
        trade_plan=SimpleNamespace(
            decision=RiskDecision.APPROVE,
            entry_price=4003.0,
            stop_loss=4001.0,
            take_profit=4007.0,
            position_size=0.01,
        ),
    )


def _pending_result() -> OrderResult:
    return OrderResult(
        timestamp=datetime.now(UTC),
        status=OrderStatus.PENDING,
        ticket=987654,
        executed_price=0.0,
        message="PLACED [10008]: accepted",
        retcode=10008,
    )


def _enabled_engine() -> LiveTradingEngine:
    engine = LiveTradingEngine(
        LiveTradingConfig(live_execution_enabled=True)
    )
    engine.state.running = True
    engine.pipeline.process_bar = Mock(return_value=_approved())
    engine.executor.is_connected = Mock(return_value=True)
    engine.adapter.adapt = Mock(
        return_value=SimpleNamespace(
            order_request=object(),
        )
    )
    return engine


def test_pending_result_blocks_future_execution() -> None:
    engine = _enabled_engine()
    engine.executor.execute_order = Mock(return_value=_pending_result())

    result = engine.process_bar(
        _bar(),
        account_balance=10_000.0,
        stop_loss_distance=2.0,
        pip_value=1.0,
    )

    assert result.trade_executed is False
    assert result.execution_result.status is OrderStatus.PENDING
    assert engine.state.active_order_count == 1
    assert engine.state.last_ticket == 987654


def test_active_order_guard_prevents_duplicate_submission() -> None:
    engine = _enabled_engine()
    engine.state.active_order_count = 1
    engine.executor.execute_order = Mock()

    result = engine.process_bar(
        _bar(),
        account_balance=10_000.0,
        stop_loss_distance=2.0,
        pip_value=1.0,
    )

    assert result.trade_executed is False
    assert result.execution_result is None
    engine.executor.execute_order.assert_not_called()


def test_broker_reconciliation_clears_active_order_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    engine.state.active_order_count = 1
    monkeypatch.setattr(
        live_engine_module,
        "get_active_order_count",
        lambda symbol: 0,
    )

    assert engine.synchronize_active_orders() == 0
    assert engine.state.active_order_count == 0


def test_active_order_query_failure_preserves_existing_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    engine.state.active_order_count = 1

    def fail(symbol: str) -> int:
        raise RuntimeError("Unable to retrieve active MT5 orders")

    monkeypatch.setattr(
        live_engine_module,
        "get_active_order_count",
        fail,
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to retrieve active MT5 orders",
    ):
        engine.synchronize_active_orders()

    assert engine.state.active_order_count == 1
