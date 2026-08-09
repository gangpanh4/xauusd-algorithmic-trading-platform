from __future__ import annotations

from types import SimpleNamespace

import pytest

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
):
    with _authorize_broker_mutation():
        return orders.send_order(request, config)


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
