"""
MT5 Order validation.
"""

from __future__ import annotations

from datetime import UTC, datetime

import MetaTrader5 as mt5

from .config import MT5ExecutionConfig
from .models import (
    OrderRequest,
    OrderResult,
    OrderSide,
    OrderStatus,
    SymbolInfo,
)
from .symbols import get_symbol_info


def validate_order(
    request: OrderRequest,
    symbol: SymbolInfo,
) -> tuple[bool, str]:
    """
    Validate an order before execution.
    """

    if not symbol.trade_allowed:
        return (
            False,
            "Trading is disabled for this symbol.",
        )

    if request.volume < symbol.volume_min:
        return (
            False,
            "Volume below minimum.",
        )

    if request.volume > symbol.volume_max:
        return (
            False,
            "Volume above maximum.",
        )

    return (
        True,
        "Order validation successful.",
    )


def build_mt5_request(
    request: OrderRequest,
    *,
    magic_number: int,
    deviation: int,
) -> dict:
    """
    Build an MT5 trade request dictionary.
    """

    order_type = (
        mt5.ORDER_TYPE_BUY
        if request.side == OrderSide.BUY
        else mt5.ORDER_TYPE_SELL
    )

    price = get_market_price(
        request.symbol,
        request.side,
    )

    return {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": request.symbol,
        "volume": request.volume,
        "type": order_type,
        "price": price,
        "sl": request.stop_loss,
        "tp": request.take_profit,
        "deviation": deviation,
        "magic": magic_number,
        "comment": request.comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }


def send_order(
    request: OrderRequest,
    config: MT5ExecutionConfig,
) -> OrderResult:
    """
    Validate and execute an MT5 order.
    """

    symbol = get_symbol_info(
        request.symbol,
    )

    valid, message = validate_order(
        request,
        symbol,
    )

    if not valid:
        return OrderResult(
            timestamp=datetime.now(UTC),
            status=OrderStatus.REJECTED,
            ticket=None,
            executed_price=0.0,
            message=message,
        )

    if request.volume != 0.01:
        return OrderResult(
            timestamp=datetime.now(UTC),
            status=OrderStatus.REJECTED,
            ticket=None,
            executed_price=0.0,
            message="Safety lock: only 0.01 lots allowed.",
        )

    mt5_request = build_mt5_request(
        request,
        magic_number=config.magic_number,
        deviation=config.default_slippage,
    )

    result = mt5.order_send(
        mt5_request,
    )

    if result is None:
        return OrderResult(
            timestamp=datetime.now(UTC),
            status=OrderStatus.REJECTED,
            ticket=None,
            executed_price=0.0,
            message=str(
                mt5.last_error(),
            ),
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


def get_market_price(
    symbol: str,
    side: OrderSide,
) -> float:
    """
    Retrieve the current executable market price.
    """

    tick = mt5.symbol_info_tick(symbol)

    if tick is None:
        error = mt5.last_error()
        raise RuntimeError(
            f"Unable to retrieve market price for "
            f"{symbol}: {error}"
        )

    if side is OrderSide.BUY:
        return tick.ask

    return tick.bid