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


def test_order_execution_is_fully_mocked_and_maps_fill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.01,
        entry_price=3300.0,
        stop_loss=3298.0,
        take_profit=3304.0,
        comment="Offline Execution Test",
    )
    monkeypatch.setattr(
        orders,
        "get_symbol_info",
        lambda name: _symbol(),
    )
    monkeypatch.setattr(
        orders.mt5,
        "order_check",
        lambda payload: SimpleNamespace(
            retcode=0,
            comment="Done",
        ),
    )
    monkeypatch.setattr(
        orders.mt5,
        "order_send",
        lambda payload: SimpleNamespace(
            retcode=orders.mt5.TRADE_RETCODE_DONE,
            order=987654,
            price=payload["price"],
            volume=payload["volume"],
            comment="Executed",
        ),
    )

    result = orders.send_order(
        request,
        MT5ExecutionConfig(),
    )

    assert result.status is OrderStatus.FILLED
    assert result.ticket == 987654
    assert result.executed_price == pytest.approx(3300.0)
    assert result.executed_volume == pytest.approx(0.01)
