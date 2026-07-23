from __future__ import annotations

import pytest

from core.mt5_execution.models import (
    OrderRequest,
    OrderSide,
    SymbolInfo,
)
from core.mt5_execution.orders import validate_order


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


def test_valid_buy_order_passes_without_mt5_connection() -> None:
    request = OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.01,
        entry_price=3300.0,
        stop_loss=3298.0,
        take_profit=3304.0,
    )

    valid, message = validate_order(request, _symbol())

    assert valid is True
    assert message == "Order validation successful."


@pytest.mark.parametrize(
    ("stop_loss", "take_profit", "message"),
    [
        (3301.0, 3304.0, "BUY stop loss must be below entry price."),
        (3298.0, 3299.0, "BUY take profit must be above entry price."),
    ],
)
def test_invalid_buy_price_relationships_are_rejected(
    stop_loss: float,
    take_profit: float,
    message: str,
) -> None:
    request = OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.01,
        entry_price=3300.0,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )

    valid, actual = validate_order(request, _symbol())

    assert valid is False
    assert actual == message
