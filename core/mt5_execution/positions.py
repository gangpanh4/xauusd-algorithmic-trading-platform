"""
MT5 Position management.
"""

from __future__ import annotations

import MetaTrader5 as mt5

from .models import (
    OrderSide,
    PositionInfo,
)


def get_open_positions() -> list[PositionInfo]:
    """
    Retrieve all open MT5 positions.
    """

    positions = mt5.positions_get()

    if positions is None:
        return []

    results: list[PositionInfo] = []

    for position in positions:

        side = (
            OrderSide.BUY
            if position.type == mt5.POSITION_TYPE_BUY
            else OrderSide.SELL
        )

        results.append(
            PositionInfo(
                ticket=position.ticket,
                symbol=position.symbol,
                side=side,
                volume=position.volume,
                open_price=position.price_open,
                stop_loss=position.sl,
                take_profit=position.tp,
                profit=position.profit,
            )
        )

    return results