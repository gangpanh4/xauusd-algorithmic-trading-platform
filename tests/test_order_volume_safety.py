from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.mt5_execution.config import MT5ExecutionConfig
from core.mt5_execution.models import (
    OrderRequest,
    OrderSide,
    OrderStatus,
    SymbolInfo,
)
import core.mt5_execution.orders as orders


def _request(volume: float) -> OrderRequest:
    return OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=volume,
        entry_price=3300.0,
        stop_loss=3295.0,
        take_profit=3310.0,
        comment="Offline safety-lock test",
    )


def _tradable_symbol() -> SymbolInfo:
    return SymbolInfo(
        name="XAUUSD",
        digits=2,
        point=0.01,
        spread=20,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        trade_allowed=True,
    )


def test_default_safety_lock_rejects_larger_volume_before_order_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        orders,
        "get_symbol_info",
        lambda symbol: _tradable_symbol(),
    )
    order_send = pytest.MonkeyPatch()
    send_calls: list[dict] = []

    monkeypatch.setattr(
        orders.mt5,
        "order_send",
        lambda request: send_calls.append(request),
    )

    result = orders.send_order(
        _request(0.02),
        MT5ExecutionConfig(),
    )

    assert result.status is OrderStatus.REJECTED
    assert result.ticket is None
    assert result.executed_price == 0.0
    assert result.message == "Safety lock: only 0.01 lots allowed."
    assert send_calls == []


def test_default_safety_lock_allows_exact_configured_volume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        orders,
        "get_symbol_info",
        lambda symbol: _tradable_symbol(),
    )
    monkeypatch.setattr(
        orders.mt5,
        "order_send",
        lambda request: SimpleNamespace(
            retcode=orders.mt5.TRADE_RETCODE_DONE,
            order=123456,
            price=request["price"],
            comment="filled",
        ),
    )

    result = orders.send_order(
        _request(0.01),
        MT5ExecutionConfig(),
    )

    assert result.status is OrderStatus.FILLED
    assert result.ticket == 123456
    assert result.executed_price == 3300.0


def test_custom_safety_lock_value_is_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        orders,
        "get_symbol_info",
        lambda symbol: _tradable_symbol(),
    )
    send_calls: list[dict] = []
    monkeypatch.setattr(
        orders.mt5,
        "order_send",
        lambda request: send_calls.append(request),
    )

    config = MT5ExecutionConfig(allowed_order_volume=0.02)

    rejected = orders.send_order(
        _request(0.01),
        config,
    )

    assert rejected.status is OrderStatus.REJECTED
    assert rejected.message == "Safety lock: only 0.02 lots allowed."
    assert send_calls == []


@pytest.mark.parametrize(
    "invalid_value",
    [0.0, -0.01, float("nan"), float("inf")],
)
def test_invalid_safety_lock_configuration_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    invalid_value: float,
) -> None:
    monkeypatch.setattr(
        orders,
        "get_symbol_info",
        lambda symbol: _tradable_symbol(),
    )
    send_calls: list[dict] = []
    monkeypatch.setattr(
        orders.mt5,
        "order_send",
        lambda request: send_calls.append(request),
    )

    result = orders.send_order(
        _request(0.01),
        MT5ExecutionConfig(allowed_order_volume=invalid_value),
    )

    assert result.status is OrderStatus.REJECTED
    assert result.message == "Safety lock configuration is invalid."
    assert send_calls == []


def test_binary_float_noise_does_not_trigger_false_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        orders,
        "get_symbol_info",
        lambda symbol: _tradable_symbol(),
    )
    monkeypatch.setattr(
        orders.mt5,
        "order_send",
        lambda request: SimpleNamespace(
            retcode=orders.mt5.TRADE_RETCODE_DONE,
            order=654321,
            price=request["price"],
            comment="filled",
        ),
    )

    result = orders.send_order(
        _request(0.010000000000000002),
        MT5ExecutionConfig(allowed_order_volume=0.01),
    )

    assert result.status is OrderStatus.FILLED
    assert result.ticket == 654321
