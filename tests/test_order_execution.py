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


def _request(side: OrderSide = OrderSide.BUY) -> OrderRequest:
    if side is OrderSide.BUY:
        return OrderRequest(
            symbol="XAUUSD",
            side=side,
            volume=0.01,
            entry_price=3300.0,
            stop_loss=3298.0,
            take_profit=3304.0,
            comment="Offline Execution Test",
        )

    return OrderRequest(
        symbol="XAUUSD",
        side=side,
        volume=0.01,
        entry_price=3300.0,
        stop_loss=3302.0,
        take_profit=3296.0,
        comment="Offline Execution Test",
    )


def _authorized_send_order(
    request: OrderRequest,
    config: MT5ExecutionConfig,
):
    with _authorize_broker_mutation():
        return orders.send_order(request, config)


def _mock_successful_broker(
    monkeypatch: pytest.MonkeyPatch,
    *,
    market_price: float,
) -> dict:
    captured: dict = {}

    monkeypatch.setattr(
        orders,
        "get_symbol_info",
        lambda name: _symbol(),
    )
    monkeypatch.setattr(
        orders,
        "get_market_price",
        lambda symbol, side: market_price,
    )
    monkeypatch.setattr(
        orders.mt5,
        "order_check",
        lambda payload: SimpleNamespace(
            retcode=0,
            comment="Done",
        ),
    )

    def fake_order_send(payload):
        captured.update(payload)
        return SimpleNamespace(
            retcode=orders.mt5.TRADE_RETCODE_DONE,
            order=987654,
            price=payload["price"],
            volume=payload["volume"],
            comment="Executed",
        )

    monkeypatch.setattr(orders.mt5, "order_send", fake_order_send)
    return captured


def test_order_execution_is_fully_mocked_and_maps_fill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _mock_successful_broker(
        monkeypatch,
        market_price=3300.0,
    )

    result = _authorized_send_order(
        _request(),
        MT5ExecutionConfig(),
    )

    assert result.status is OrderStatus.FILLED
    assert result.ticket == 987654
    assert result.executed_price == pytest.approx(3300.0)
    assert result.executed_volume == pytest.approx(0.01)
    assert captured["price"] == pytest.approx(3300.0)
    assert captured["sl"] == pytest.approx(3298.0)
    assert captured["tp"] == pytest.approx(3304.0)


def test_buy_uses_current_ask_and_recenters_exit_distances(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _mock_successful_broker(
        monkeypatch,
        market_price=3300.05,
    )

    result = _authorized_send_order(
        _request(OrderSide.BUY),
        MT5ExecutionConfig(default_slippage=10),
    )

    assert result.status is OrderStatus.FILLED
    assert captured["price"] == pytest.approx(3300.05)
    assert captured["sl"] == pytest.approx(3298.05)
    assert captured["tp"] == pytest.approx(3304.05)


def test_sell_uses_current_bid_and_recenters_exit_distances(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _mock_successful_broker(
        monkeypatch,
        market_price=3299.95,
    )

    result = _authorized_send_order(
        _request(OrderSide.SELL),
        MT5ExecutionConfig(default_slippage=10),
    )

    assert result.status is OrderStatus.FILLED
    assert captured["price"] == pytest.approx(3299.95)
    assert captured["sl"] == pytest.approx(3301.95)
    assert captured["tp"] == pytest.approx(3295.95)


def test_buy_rejects_adverse_movement_beyond_configured_deviation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(orders, "get_symbol_info", lambda name: _symbol())
    monkeypatch.setattr(
        orders,
        "get_market_price",
        lambda symbol, side: 3300.11,
    )
    order_check = pytest.fail
    order_send = pytest.fail
    monkeypatch.setattr(orders.mt5, "order_check", order_check)
    monkeypatch.setattr(orders.mt5, "order_send", order_send)

    result = _authorized_send_order(
        _request(OrderSide.BUY),
        MT5ExecutionConfig(default_slippage=10),
    )

    assert result.status is OrderStatus.REJECTED
    assert "approved adverse-entry deviation" in result.message


def test_sell_rejects_adverse_movement_beyond_configured_deviation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(orders, "get_symbol_info", lambda name: _symbol())
    monkeypatch.setattr(
        orders,
        "get_market_price",
        lambda symbol, side: 3299.89,
    )
    monkeypatch.setattr(orders.mt5, "order_check", pytest.fail)
    monkeypatch.setattr(orders.mt5, "order_send", pytest.fail)

    result = _authorized_send_order(
        _request(OrderSide.SELL),
        MT5ExecutionConfig(default_slippage=10),
    )

    assert result.status is OrderStatus.REJECTED
    assert "approved adverse-entry deviation" in result.message


def test_favorable_movement_is_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _mock_successful_broker(
        monkeypatch,
        market_price=3299.50,
    )

    result = _authorized_send_order(
        _request(OrderSide.BUY),
        MT5ExecutionConfig(default_slippage=0),
    )

    assert result.status is OrderStatus.FILLED
    assert captured["price"] == pytest.approx(3299.50)
    assert captured["sl"] == pytest.approx(3297.50)
    assert captured["tp"] == pytest.approx(3303.50)


def test_zero_deviation_rejects_any_adverse_movement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(orders, "get_symbol_info", lambda name: _symbol())
    monkeypatch.setattr(
        orders,
        "get_market_price",
        lambda symbol, side: 3300.01,
    )
    monkeypatch.setattr(orders.mt5, "order_check", pytest.fail)
    monkeypatch.setattr(orders.mt5, "order_send", pytest.fail)

    result = _authorized_send_order(
        _request(OrderSide.BUY),
        MT5ExecutionConfig(default_slippage=0),
    )

    assert result.status is OrderStatus.REJECTED
    assert "approved adverse-entry deviation" in result.message


def test_market_quote_failure_rejects_before_broker_submission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(orders, "get_symbol_info", lambda name: _symbol())

    def fail_quote(symbol, side):
        raise RuntimeError("quote unavailable")

    monkeypatch.setattr(orders, "get_market_price", fail_quote)
    monkeypatch.setattr(orders.mt5, "order_check", pytest.fail)
    monkeypatch.setattr(orders.mt5, "order_send", pytest.fail)

    result = _authorized_send_order(
        _request(OrderSide.BUY),
        MT5ExecutionConfig(),
    )

    assert result.status is OrderStatus.REJECTED
    assert "quote unavailable" in result.message
