from __future__ import annotations

from types import SimpleNamespace

import pytest

import core.mt5_execution.orders as orders
from core.mt5_execution.config import MT5ExecutionConfig
from core.mt5_execution.models import (
    OrderRequest,
    OrderSide,
    OrderStatus,
    SymbolInfo,
)


def _symbol(*, flags: int, execution_mode: int) -> SymbolInfo:
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
        filling_mode_flags=flags,
        trade_execution_mode=execution_mode,
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


def test_fok_is_preferred_when_both_fok_and_ioc_are_supported() -> None:
    symbol = _symbol(flags=3, execution_mode=2)

    request = orders.build_mt5_request(
        _request(),
        magic_number=30001,
        deviation=10,
        symbol=symbol,
    )

    assert request["type_filling"] == orders.mt5.ORDER_FILLING_FOK


def test_ioc_is_used_when_fok_is_not_supported() -> None:
    symbol = _symbol(flags=2, execution_mode=2)

    request = orders.build_mt5_request(
        _request(),
        magic_number=30001,
        deviation=10,
        symbol=symbol,
    )

    assert request["type_filling"] == orders.mt5.ORDER_FILLING_IOC


def test_return_is_used_outside_market_execution_when_flags_are_empty() -> None:
    instant_execution = getattr(
        orders.mt5,
        "SYMBOL_TRADE_EXECUTION_INSTANT",
        1,
    )
    symbol = _symbol(flags=0, execution_mode=instant_execution)

    request = orders.build_mt5_request(
        _request(),
        magic_number=30001,
        deviation=10,
        symbol=symbol,
    )

    assert request["type_filling"] == orders.mt5.ORDER_FILLING_RETURN


def test_market_execution_without_fok_or_ioc_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    market_execution = getattr(
        orders.mt5,
        "SYMBOL_TRADE_EXECUTION_MARKET",
        2,
    )
    symbol = _symbol(flags=0, execution_mode=market_execution)
    monkeypatch.setattr(orders, "get_symbol_info", lambda name: symbol)

    send_calls: list[dict] = []
    monkeypatch.setattr(
        orders.mt5,
        "order_send",
        lambda request: send_calls.append(request),
    )

    result = orders.send_order(_request(), MT5ExecutionConfig())

    assert result.status is OrderStatus.REJECTED
    assert "No supported filling mode" in result.message
    assert send_calls == []


@pytest.mark.parametrize("invalid_flags", [-1, 1.5, True])
def test_invalid_filling_flags_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    invalid_flags,
) -> None:
    symbol = _symbol(flags=0, execution_mode=2)
    object.__setattr__(symbol, "filling_mode_flags", invalid_flags)
    monkeypatch.setattr(orders, "get_symbol_info", lambda name: symbol)

    send_calls: list[dict] = []
    monkeypatch.setattr(
        orders.mt5,
        "order_send",
        lambda request: send_calls.append(request),
    )

    result = orders.send_order(_request(), MT5ExecutionConfig())

    assert result.status is OrderStatus.REJECTED
    assert "filling mode flags are invalid" in result.message
    assert send_calls == []


def test_selected_filling_mode_reaches_order_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    symbol = _symbol(flags=2, execution_mode=2)
    monkeypatch.setattr(
        orders.mt5,
        "order_check",
        lambda request: SimpleNamespace(retcode=0, comment="Done"),
    )
    monkeypatch.setattr(orders, "get_symbol_info", lambda name: symbol)

    captured: dict = {}

    def fake_send(request):
        captured.update(request)
        return SimpleNamespace(
            retcode=orders.mt5.TRADE_RETCODE_DONE,
            order=123,
            price=request["price"],
            comment="filled",
        )

    monkeypatch.setattr(orders.mt5, "order_send", fake_send)

    result = orders.send_order(_request(), MT5ExecutionConfig())

    assert result.status is OrderStatus.FILLED
    assert captured["type_filling"] == orders.mt5.ORDER_FILLING_IOC
