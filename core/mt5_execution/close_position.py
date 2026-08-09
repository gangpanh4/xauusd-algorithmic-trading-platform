"""MT5 position closing with broker preflight and retcode handling."""

from __future__ import annotations

from datetime import UTC, datetime
from math import isfinite

import MetaTrader5 as mt5

from .authority import _require_broker_mutation_authority
from .config import MT5ExecutionConfig
from .models import OrderResult, OrderSide, OrderStatus
from .orders import (
    _aligned_to_step,
    _map_trade_retcode,
    _normalize_price,
    _retcode_name,
    _select_filling_mode,
)
from .positions import get_position
from .symbols import get_symbol_info


def close_position(
    ticket: int,
    config: MT5ExecutionConfig,
) -> OrderResult:
    """Close one existing MT5 position using the full remaining volume."""

    _require_broker_mutation_authority()

    if isinstance(ticket, bool) or not isinstance(ticket, int) or ticket <= 0:
        return _rejected("Position ticket must be a positive integer.")

    position = get_position(ticket)
    if position is None:
        return _rejected("Position not found.")

    symbol = get_symbol_info(position.symbol)
    if not symbol.trade_allowed:
        return _rejected("Trading is disabled for this symbol.")

    valid_volume, volume_message = _validate_close_volume(
        position.volume,
        minimum=symbol.volume_min,
        maximum=symbol.volume_max,
        step=symbol.volume_step,
    )
    if not valid_volume:
        return _rejected(volume_message)

    tick = mt5.symbol_info_tick(position.symbol)
    if tick is None:
        return _rejected(
            f"Unable to retrieve close price: {mt5.last_error()}"
        )

    if position.side is OrderSide.BUY:
        order_type = mt5.ORDER_TYPE_SELL
        raw_price = tick.bid
    elif position.side is OrderSide.SELL:
        order_type = mt5.ORDER_TYPE_BUY
        raw_price = tick.ask
    else:
        return _rejected("Unsupported position side.")

    try:
        price = _normalize_price(float(raw_price), symbol)
        filling_mode = _select_filling_mode(symbol)
    except (TypeError, ValueError) as exc:
        return _rejected(f"Close request rejected: {exc}")

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
        "type_filling": filling_mode,
    }

    check_result = mt5.order_check(request)
    if check_result is None:
        return _rejected(
            f"Close preflight unavailable: {mt5.last_error()}"
        )

    check_retcode = int(getattr(check_result, "retcode", -1))
    check_comment = str(
        getattr(check_result, "comment", "No preflight comment.")
    )
    if check_retcode != 0:
        return OrderResult(
            timestamp=datetime.now(UTC),
            status=OrderStatus.REJECTED,
            ticket=None,
            executed_price=0.0,
            message=(
                f"Close preflight rejected [{check_retcode}]: "
                f"{check_comment}"
            ),
            retcode=check_retcode,
        )

    result = mt5.order_send(request)
    if result is None:
        return _rejected(
            f"Close submission unavailable: {mt5.last_error()}"
        )

    retcode = int(getattr(result, "retcode", -1))
    status = _map_trade_retcode(retcode)
    result_ticket = getattr(result, "order", None)
    executed_price = float(getattr(result, "price", 0.0))
    executed_volume = float(getattr(result, "volume", 0.0))
    comment = str(getattr(result, "comment", "No broker comment."))

    return OrderResult(
        timestamp=datetime.now(UTC),
        status=status,
        ticket=result_ticket,
        executed_price=executed_price,
        message=f"{_retcode_name(retcode)} [{retcode}]: {comment}",
        retcode=retcode,
        executed_volume=executed_volume,
    )


def _validate_close_volume(
    volume: float,
    *,
    minimum: float,
    maximum: float,
    step: float,
) -> tuple[bool, str]:
    values = {
        "Position volume": volume,
        "Broker minimum volume": minimum,
        "Broker maximum volume": maximum,
        "Broker volume step": step,
    }
    for name, value in values.items():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(float(value))
        ):
            return False, f"{name} must be finite."

    if volume <= 0.0:
        return False, "Position volume must be greater than zero."
    if volume < minimum:
        return False, "Position volume is below broker minimum."
    if volume > maximum:
        return False, "Position volume is above broker maximum."
    if not _aligned_to_step(volume, step=step, origin=minimum):
        return False, "Position volume is not aligned to broker volume step."

    return True, "Close volume validation successful."


def _rejected(message: str) -> OrderResult:
    return OrderResult(
        timestamp=datetime.now(UTC),
        status=OrderStatus.REJECTED,
        ticket=None,
        executed_price=0.0,
        message=message,
    )
