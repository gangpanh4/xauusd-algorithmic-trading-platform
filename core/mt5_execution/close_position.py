"""
MT5 Position closing.
"""

from __future__ import annotations

from datetime import UTC, datetime

import MetaTrader5 as mt5

from .config import MT5ExecutionConfig
from .models import (
    OrderResult,
    OrderSide,
    OrderStatus,
)
from .positions import (
    get_position,
)



def close_position(
    ticket: int,
    config: MT5ExecutionConfig,
) -> OrderResult:
    """
    Close an existing MT5 position.
    """

    position = get_position(ticket)

    if position is None:

        return OrderResult(
            timestamp=datetime.now(UTC),
            status=OrderStatus.REJECTED,
            ticket=None,
            executed_price=0.0,
            message="Position not found.",
        )

    tick = mt5.symbol_info_tick(
        position.symbol,
    )

    if tick is None:

        return OrderResult(
            timestamp=datetime.now(UTC),
            status=OrderStatus.REJECTED,
            ticket=None,
            executed_price=0.0,
            message=str(mt5.last_error()),
        )

    if position.side is OrderSide.BUY:

        order_type = mt5.ORDER_TYPE_SELL
        price = tick.bid

    else:

        order_type = mt5.ORDER_TYPE_BUY
        price = tick.ask

    request = {

        "action": mt5.TRADE_ACTION_DEAL,

        "symbol": position.symbol,

        "position": position.ticket,

        "volume": position.volume,

        "type": order_type,

        "price": price,

        "deviation": config.default_slippage,

        "magic": config.magic_number,

        "comment": "Close Position",

        "type_time": mt5.ORDER_TIME_GTC,

        "type_filling": mt5.ORDER_FILLING_FOK,
    }

    result = mt5.order_send(
        request,
    )

    if result is None:

        return OrderResult(
            timestamp=datetime.now(UTC),
            status=OrderStatus.REJECTED,
            ticket=None,
            executed_price=0.0,
            message=str(mt5.last_error()),
        )

    status = (
        OrderStatus.FILLED
        if result.retcode == mt5.TRADE_RETCODE_DONE
        else OrderStatus.REJECTED
    )

    return OrderResult(
        timestamp=datetime.now(UTC),
        status=status,
        ticket=result.order,
        executed_price=result.price,
        message=f"{result.retcode}: {result.comment}",
    )