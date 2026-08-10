from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.live_trading.demo_execution_authorization import (
    DemoExecutionAuthorization,
    validate_demo_execution_authorization_time_window,
)
from core.mt5_execution import orders
from core.mt5_execution.authority import _authorize_broker_mutation
from core.mt5_execution.config import MT5ExecutionConfig
from core.mt5_execution.models import (
    OrderRequest,
    OrderSide,
    OrderStatus,
    SymbolInfo,
)


def _symbol() -> SymbolInfo:
    return SymbolInfo(
        name="XAUUSD",
        digits=2,
        point=0.01,
        spread=20,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        trade_allowed=True,
        tick_size=0.01,
        minimum_stop_distance=0.01,
        filling_mode_flags=1,
        trade_execution_mode=2,
    )


def _request() -> OrderRequest:
    return OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.01,
        entry_price=3300.0,
        stop_loss=3295.0,
        take_profit=3310.0,
    )


def _authorized_send_order(
    request: OrderRequest,
    config: MT5ExecutionConfig,
    *,
    pre_send_guard: Callable[[], None] | None = None,
):
    with _authorize_broker_mutation():
        return orders.send_order(
            request,
            config,
            pre_send_guard=pre_send_guard,
        )


def _mock_reference_quote(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        orders,
        "get_market_price",
        lambda symbol, side: 3300.0,
    )


def test_preflight_rejection_prevents_order_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(orders, "get_symbol_info", lambda name: _symbol())
    _mock_reference_quote(monkeypatch)
    monkeypatch.setattr(
        orders.mt5,
        "order_check",
        lambda request: SimpleNamespace(
            retcode=10019,
            comment="Not enough money",
        ),
    )
    sends: list[dict] = []
    monkeypatch.setattr(
        orders.mt5,
        "order_send",
        lambda request: sends.append(request),
    )

    result = _authorized_send_order(_request(), MT5ExecutionConfig())

    assert result.status is OrderStatus.REJECTED
    assert result.retcode == 10019
    assert "Order preflight rejected [10019]" in result.message
    assert sends == []


def test_missing_preflight_result_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(orders, "get_symbol_info", lambda name: _symbol())
    _mock_reference_quote(monkeypatch)
    monkeypatch.setattr(orders.mt5, "order_check", lambda request: None)
    monkeypatch.setattr(
        orders.mt5,
        "last_error",
        lambda: (-10005, "IPC timeout"),
    )
    sends: list[dict] = []
    monkeypatch.setattr(
        orders.mt5,
        "order_send",
        lambda request: sends.append(request),
    )

    result = _authorized_send_order(_request(), MT5ExecutionConfig())

    assert result.status is OrderStatus.REJECTED
    assert "Order preflight unavailable" in result.message
    assert sends == []


def test_successful_preflight_allows_submission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(orders, "get_symbol_info", lambda name: _symbol())
    _mock_reference_quote(monkeypatch)
    monkeypatch.setattr(
        orders.mt5,
        "order_check",
        lambda request: SimpleNamespace(retcode=0, comment="Done"),
    )
    monkeypatch.setattr(
        orders.mt5,
        "order_send",
        lambda request: SimpleNamespace(
            retcode=orders.mt5.TRADE_RETCODE_DONE,
            order=123,
            price=request["price"],
            volume=request["volume"],
            comment="Request executed",
        ),
    )

    result = _authorized_send_order(_request(), MT5ExecutionConfig())

    assert result.status is OrderStatus.FILLED
    assert result.ticket == 123
    assert result.executed_volume == pytest.approx(0.01)

def _deadline_authorization(
    *,
    now: datetime,
    expires_at: datetime,
) -> DemoExecutionAuthorization:
    return DemoExecutionAuthorization(
        schema_version=1,
        authorization_id="deadline-test",
        issued_at=now - timedelta(minutes=1),
        expires_at=expires_at,
        account_login=123456,
        account_server="MetaQuotes-Demo",
        symbol="XAUUSD",
        maximum_volume=0.01,
        maximum_submissions=1,
        demo_only=True,
        one_shot=True,
        acknowledgement="I AUTHORIZE ONE DEMO ORDER",
    )


def test_final_guard_runs_after_order_check_and_before_order_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(orders, "get_symbol_info", lambda name: _symbol())
    _mock_reference_quote(monkeypatch)
    events: list[str] = []
    monkeypatch.setattr(
        orders.mt5,
        "order_check",
        lambda request: (
            events.append("order_check")
            or SimpleNamespace(retcode=0, comment="Done")
        ),
    )
    monkeypatch.setattr(
        orders.mt5,
        "order_send",
        lambda request: (
            events.append("order_send")
            or SimpleNamespace(
                retcode=orders.mt5.TRADE_RETCODE_DONE,
                order=123,
                price=request["price"],
                volume=request["volume"],
                comment="Request executed",
            )
        ),
    )

    def guard() -> None:
        events.append("guard")

    result = _authorized_send_order(
        _request(),
        MT5ExecutionConfig(),
        pre_send_guard=guard,
    )

    assert result.status is OrderStatus.FILLED
    assert events == ["order_check", "guard", "order_send"]


def test_authorization_expiring_during_order_check_blocks_order_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = datetime(2026, 8, 10, 7, 0, tzinfo=UTC)
    authorization = _deadline_authorization(
        now=base,
        expires_at=base + timedelta(seconds=1),
    )
    current = [base]
    monkeypatch.setattr(orders, "get_symbol_info", lambda name: _symbol())
    _mock_reference_quote(monkeypatch)

    def order_check(request):
        current[0] = authorization.expires_at + timedelta(microseconds=1)
        return SimpleNamespace(retcode=0, comment="Done")

    send = Mock()
    monkeypatch.setattr(orders.mt5, "order_check", order_check)
    monkeypatch.setattr(orders.mt5, "order_send", send)

    def guard() -> None:
        validate_demo_execution_authorization_time_window(
            authorization,
            now=current[0],
        )

    result = _authorized_send_order(
        _request(),
        MT5ExecutionConfig(),
        pre_send_guard=guard,
    )

    assert result.status is OrderStatus.REJECTED
    assert "expired" in result.message
    send.assert_not_called()


def test_authorization_expired_one_instant_before_send_is_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = datetime(2026, 8, 10, 7, 0, tzinfo=UTC)
    authorization = _deadline_authorization(
        now=base,
        expires_at=base + timedelta(seconds=1),
    )
    monkeypatch.setattr(orders, "get_symbol_info", lambda name: _symbol())
    _mock_reference_quote(monkeypatch)
    monkeypatch.setattr(
        orders.mt5,
        "order_check",
        lambda request: SimpleNamespace(retcode=0, comment="Done"),
    )
    send = Mock()
    monkeypatch.setattr(orders.mt5, "order_send", send)

    def guard() -> None:
        validate_demo_execution_authorization_time_window(
            authorization,
            now=authorization.expires_at + timedelta(microseconds=1),
        )

    result = _authorized_send_order(
        _request(),
        MT5ExecutionConfig(),
        pre_send_guard=guard,
    )

    assert result.status is OrderStatus.REJECTED
    assert "expired" in result.message
    send.assert_not_called()
