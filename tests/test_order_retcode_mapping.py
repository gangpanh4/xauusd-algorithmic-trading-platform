from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from core.mt5_execution import orders
from core.mt5_execution.config import MT5ExecutionConfig
from core.mt5_execution.models import (
    OrderRequest,
    OrderSide,
    OrderStatus,
    SymbolInfo,
)


def _request() -> OrderRequest:
    return OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.01,
        entry_price=3300.0,
        stop_loss=3298.0,
        take_profit=3304.0,
        comment="Offline acknowledgement test",
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


def _send_with_response(
    monkeypatch: pytest.MonkeyPatch,
    response: object | None,
):
    monkeypatch.setattr(orders, "get_symbol_info", lambda symbol: _symbol())
    monkeypatch.setattr(
        orders,
        "get_market_price",
        lambda symbol, side: 3300.0,
    )
    monkeypatch.setattr(
        orders.mt5,
        "order_check",
        lambda request: SimpleNamespace(retcode=0, comment="Done"),
    )
    monkeypatch.setattr(orders.mt5, "order_send", lambda request: response)
    return orders.send_order(_request(), MT5ExecutionConfig())


@pytest.mark.parametrize(
    ("retcode", "expected"),
    [
        (orders.mt5.TRADE_RETCODE_DONE, OrderStatus.FILLED),
        (
            getattr(orders.mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010),
            OrderStatus.PARTIALLY_FILLED,
        ),
        (
            getattr(orders.mt5, "TRADE_RETCODE_PLACED", 10008),
            OrderStatus.PENDING,
        ),
        (
            getattr(orders.mt5, "TRADE_RETCODE_CANCEL", 10007),
            OrderStatus.CANCELLED,
        ),
        (
            getattr(orders.mt5, "TRADE_RETCODE_INVALID_STOPS", 10016),
            OrderStatus.REJECTED,
        ),
        (
            getattr(orders.mt5, "TRADE_RETCODE_NO_MONEY", 10019),
            OrderStatus.REJECTED,
        ),
    ],
)
def test_trade_retcode_mapping(retcode: int, expected: OrderStatus) -> None:
    assert orders._map_trade_retcode(retcode) is expected


def test_unknown_retcode_is_rejected_and_named() -> None:
    assert orders._map_trade_retcode(999999) is OrderStatus.REJECTED
    assert orders._retcode_name(999999) == "UNKNOWN_RETCODE"


@pytest.mark.parametrize(
    "executed_volume",
    [0.01, 0.010000000000000002],
)
def test_filled_acknowledgement_accepts_exact_requested_volume(
    executed_volume: float,
) -> None:
    valid, message = orders._validate_execution_acknowledgement(
        status=OrderStatus.FILLED,
        requested_volume=0.01,
        executed_volume=executed_volume,
    )

    assert valid is True
    assert "valid" in message.lower()


@pytest.mark.parametrize(
    "executed_volume",
    [0.0, -0.01, 0.005, 0.02, math.nan, math.inf, -math.inf],
)
def test_filled_acknowledgement_rejects_invalid_volume(
    executed_volume: float,
) -> None:
    valid, message = orders._validate_execution_acknowledgement(
        status=OrderStatus.FILLED,
        requested_volume=0.01,
        executed_volume=executed_volume,
    )

    assert valid is False
    assert message


def test_partial_acknowledgement_accepts_positive_subrequest_volume() -> None:
    valid, message = orders._validate_execution_acknowledgement(
        status=OrderStatus.PARTIALLY_FILLED,
        requested_volume=0.01,
        executed_volume=0.005,
    )

    assert valid is True
    assert "valid" in message.lower()


@pytest.mark.parametrize(
    "executed_volume",
    [0.0, -0.01, 0.01, 0.02, math.nan, math.inf, -math.inf],
)
def test_partial_acknowledgement_rejects_invalid_volume(
    executed_volume: float,
) -> None:
    valid, message = orders._validate_execution_acknowledgement(
        status=OrderStatus.PARTIALLY_FILLED,
        requested_volume=0.01,
        executed_volume=executed_volume,
    )

    assert valid is False
    assert message


def test_non_execution_status_does_not_require_volume_acknowledgement() -> None:
    valid, message = orders._validate_execution_acknowledgement(
        status=OrderStatus.PENDING,
        requested_volume=0.01,
        executed_volume=0.0,
    )

    assert valid is True
    assert "not required" in message.lower()


@pytest.mark.parametrize(
    ("retcode", "executed_volume"),
    [
        (orders.mt5.TRADE_RETCODE_DONE, None),
        (orders.mt5.TRADE_RETCODE_DONE, "malformed"),
        (orders.mt5.TRADE_RETCODE_DONE, 0.005),
        (
            getattr(orders.mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010),
            0.0,
        ),
        (
            getattr(orders.mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010),
            0.01,
        ),
    ],
)
def test_ambiguous_fill_like_acknowledgement_remains_pending(
    monkeypatch: pytest.MonkeyPatch,
    retcode: int,
    executed_volume: object,
) -> None:
    result = _send_with_response(
        monkeypatch,
        SimpleNamespace(
            retcode=retcode,
            order=4242,
            price=3300.0,
            volume=executed_volume,
            comment="success-like response",
        ),
    )

    assert result.status is OrderStatus.PENDING
    assert result.ticket == 4242
    assert result.retcode == retcode
    assert "ambiguous execution acknowledgement" in result.message
    assert "reconciliation is required" in result.message


def test_missing_broker_acknowledgement_remains_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _send_with_response(monkeypatch, None)

    assert result.status is OrderStatus.PENDING
    assert result.ticket is None
    assert result.retcode is None
    assert "no broker acknowledgement" in result.message
    assert "reconciliation is required" in result.message


@pytest.mark.parametrize(
    ("retcode", "executed_volume", "expected"),
    [
        (orders.mt5.TRADE_RETCODE_DONE, 0.01, OrderStatus.FILLED),
        (
            getattr(orders.mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010),
            0.004,
            OrderStatus.PARTIALLY_FILLED,
        ),
    ],
)
def test_valid_fill_like_acknowledgement_keeps_execution_status(
    monkeypatch: pytest.MonkeyPatch,
    retcode: int,
    executed_volume: float,
    expected: OrderStatus,
) -> None:
    result = _send_with_response(
        monkeypatch,
        SimpleNamespace(
            retcode=retcode,
            order=4242,
            price=3300.0,
            volume=executed_volume,
            comment="valid execution",
        ),
    )

    assert result.status is expected
    assert result.ticket == 4242
    assert result.executed_volume == pytest.approx(executed_volume)


def test_explicit_rejection_is_terminal_and_normalizes_zero_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _send_with_response(
        monkeypatch,
        SimpleNamespace(
            retcode=getattr(orders.mt5, "TRADE_RETCODE_REJECT", 10006),
            order=0,
            price=0.0,
            volume=0.0,
            comment="rejected",
        ),
    )

    assert result.status is OrderStatus.REJECTED
    assert result.ticket is None
    assert "REJECT" in result.message
