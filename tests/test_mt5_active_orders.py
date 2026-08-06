from __future__ import annotations

from types import SimpleNamespace

import MetaTrader5 as mt5

from core.mt5_execution.active_orders import (
    get_active_order_count,
    get_active_orders,
)
from core.mt5_execution.models import OrderSide


def test_get_active_orders_preserves_provenance(monkeypatch) -> None:
    raw = SimpleNamespace(
        ticket=101,
        symbol="XAUUSD",
        type=mt5.ORDER_TYPE_BUY,
        volume_initial=0.01,
        volume_current=0.01,
        price_open=4000.0,
        sl=3990.0,
        tp=4020.0,
        magic=234000,
        comment="xau:0123456789abcdef",
        time_setup=1_700_000_000,
        time_setup_msc=1_700_000_000_000,
    )
    monkeypatch.setattr(
        "core.mt5_execution.active_orders.mt5.orders_get",
        lambda **kwargs: (raw,),
    )

    orders = get_active_orders("XAUUSD")

    assert len(orders) == 1
    assert orders[0].ticket == 101
    assert orders[0].side is OrderSide.BUY
    assert orders[0].magic_number == 234000
    assert orders[0].comment == "xau:0123456789abcdef"
    assert get_active_order_count("XAUUSD") == 1


def test_get_active_orders_fails_closed_on_query_error(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.mt5_execution.active_orders.mt5.orders_get",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "core.mt5_execution.active_orders.mt5.last_error",
        lambda: (1, "failed"),
    )

    import pytest

    with pytest.raises(RuntimeError, match="Unable to retrieve"):
        get_active_orders("XAUUSD")
