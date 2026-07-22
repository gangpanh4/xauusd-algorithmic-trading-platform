from __future__ import annotations

import pytest

import core.mt5_execution.orders as orders
from core.mt5_execution.models import OrderStatus


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
