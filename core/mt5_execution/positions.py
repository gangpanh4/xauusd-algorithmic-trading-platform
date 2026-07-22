"""
MT5 Position management.
"""

from __future__ import annotations

from typing import Any

import MetaTrader5 as mt5

from .models import (
    OrderSide,
    PositionInfo,
)


def _to_position_info(
    position: Any,
) -> PositionInfo:
    """
    Convert an MT5 position into PositionInfo.
    """

    side = (
        OrderSide.BUY
        if position.type == mt5.POSITION_TYPE_BUY
        else OrderSide.SELL
    )

    return PositionInfo(
        ticket=position.ticket,
        symbol=position.symbol,
        side=side,
        volume=position.volume,
        open_price=position.price_open,
        stop_loss=position.sl,
        take_profit=position.tp,
        profit=position.profit,
    )


def get_open_positions(
    symbol: str | None = None,
) -> list[PositionInfo]:
    """
    Retrieve open MT5 positions.

    When ``symbol`` is supplied, only positions for that exact broker symbol
    are returned. The no-argument API remains backward compatible.
    """

    if symbol is not None:
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol must be a non-empty string or None")
        positions = mt5.positions_get(symbol=symbol)
    else:
        positions = mt5.positions_get()

    if positions is None:
        raise RuntimeError(
            f"Unable to retrieve open MT5 positions: {mt5.last_error()}"
        )

    return [
        _to_position_info(position)
        for position in positions
    ]


def get_position(
    ticket: int,
) -> PositionInfo | None:
    """
    Retrieve one open position by ticket.
    """

    positions = mt5.positions_get(
        ticket=ticket,
    )

    if positions is None:
        raise RuntimeError(
            f"Unable to retrieve MT5 position {ticket}: {mt5.last_error()}"
        )

    if not positions:
        return None

    return _to_position_info(
        positions[0],
    )