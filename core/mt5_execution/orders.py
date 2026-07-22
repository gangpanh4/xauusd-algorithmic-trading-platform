"""
MT5 Order validation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from math import isclose, isfinite

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
    """Validate broker-critical order fields before execution."""

    if not symbol.trade_allowed:
        return False, "Trading is disabled for this symbol."

    if request.side not in (OrderSide.BUY, OrderSide.SELL):
        return False, "Unsupported order side."

    numeric_fields = {
        "Volume": request.volume,
        "Entry price": request.entry_price,
        "Stop loss": request.stop_loss,
        "Take profit": request.take_profit,
    }
    for name, value in numeric_fields.items():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(float(value))
        ):
            return False, f"{name} must be finite."

    if request.volume <= 0.0:
        return False, "Volume must be greater than zero."
    if request.volume < symbol.volume_min:
        return False, "Volume below minimum."
    if request.volume > symbol.volume_max:
        return False, "Volume above maximum."
    if not _aligned_to_step(
        request.volume,
        step=symbol.volume_step,
        origin=symbol.volume_min,
    ):
        return False, "Volume is not aligned to broker volume step."

    if request.entry_price < 0.0:
        return False, "Entry price cannot be negative."
    if request.stop_loss <= 0.0:
        return False, "Stop loss must be greater than zero."
    if request.take_profit <= 0.0:
        return False, "Take profit must be greater than zero."

    if request.entry_price > 0.0:
        return _validate_price_relationships(
            side=request.side,
            entry_price=request.entry_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            minimum_stop_distance=symbol.minimum_stop_distance,
        )

    return True, "Order validation successful."

def build_mt5_request(
    request: OrderRequest,
    *,
    magic_number: int,
    deviation: int,
    symbol: SymbolInfo | None = None,
) -> dict:
    """
    Build an MT5 trade request dictionary.
    """

    order_type = (
        mt5.ORDER_TYPE_BUY
        if request.side == OrderSide.BUY
        else mt5.ORDER_TYPE_SELL
    )

    # Use the supplied entry price during tests/backtesting.
    # Otherwise use the live MT5 market price.
    if request.entry_price > 0:
        price = request.entry_price
    else:
        price = get_market_price(
            request.symbol,
            request.side,
        )

    if symbol is not None:
        price = _normalize_price(price, symbol)
        stop_loss = _normalize_price(request.stop_loss, symbol)
        take_profit = _normalize_price(request.take_profit, symbol)
    else:
        stop_loss = request.stop_loss
        take_profit = request.take_profit

    return {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": request.symbol,
        "volume": request.volume,
        "type": order_type,
        "price": price,
        "sl": stop_loss,
        "tp": take_profit,
        "deviation": deviation,
        "magic": magic_number,
        "comment": request.comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": (
            _select_filling_mode(symbol)
            if symbol is not None
            else mt5.ORDER_FILLING_FOK
        ),
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

    allowed_volume = config.allowed_order_volume
    if (
        isinstance(allowed_volume, bool)
        or not isinstance(allowed_volume, (int, float))
        or not isfinite(float(allowed_volume))
        or float(allowed_volume) <= 0.0
    ):
        return OrderResult(
            timestamp=datetime.now(UTC),
            status=OrderStatus.REJECTED,
            ticket=None,
            executed_price=0.0,
            message="Safety lock configuration is invalid.",
        )

    if not isclose(
        float(request.volume),
        float(allowed_volume),
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        return OrderResult(
            timestamp=datetime.now(UTC),
            status=OrderStatus.REJECTED,
            ticket=None,
            executed_price=0.0,
            message=(
                "Safety lock: only "
                f"{float(allowed_volume):g} lots allowed."
            ),
        )

    try:
        mt5_request = build_mt5_request(
            request,
            magic_number=config.magic_number,
            deviation=config.default_slippage,
            symbol=symbol,
        )
    except (TypeError, ValueError) as exc:
        return OrderResult(
            timestamp=datetime.now(UTC),
            status=OrderStatus.REJECTED,
            ticket=None,
            executed_price=0.0,
            message=f"Order request rejected: {exc}",
        )

    live_valid, live_message = _validate_price_relationships(
        side=request.side,
        entry_price=float(mt5_request["price"]),
        stop_loss=float(mt5_request["sl"]),
        take_profit=float(mt5_request["tp"]),
        minimum_stop_distance=symbol.minimum_stop_distance,
    )
    if not live_valid:
        return OrderResult(
            timestamp=datetime.now(UTC),
            status=OrderStatus.REJECTED,
            ticket=None,
            executed_price=0.0,
            message=live_message,
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




_SYMBOL_FILLING_FOK = 1
_SYMBOL_FILLING_IOC = 2


def _select_filling_mode(symbol: SymbolInfo) -> int:
    """Select a broker-supported market-order filling policy.

    ``filling_mode_flags`` is a bit mask. FOK is preferred because it preserves
    the requested position size. IOC is the fallback when FOK is unavailable.
    RETURN is used only outside Market Execution, where MT5 permits it.
    """

    flags = symbol.filling_mode_flags
    execution_mode = symbol.trade_execution_mode

    if isinstance(flags, bool) or not isinstance(flags, int) or flags < 0:
        raise ValueError("Symbol filling mode flags are invalid.")

    if flags & _SYMBOL_FILLING_FOK:
        return mt5.ORDER_FILLING_FOK

    if flags & _SYMBOL_FILLING_IOC:
        return mt5.ORDER_FILLING_IOC

    market_execution = getattr(
        mt5,
        "SYMBOL_TRADE_EXECUTION_MARKET",
        2,
    )
    if execution_mode != market_execution:
        return mt5.ORDER_FILLING_RETURN

    raise ValueError(
        "No supported filling mode is available for Market Execution."
    )

def _aligned_to_step(
    value: float,
    *,
    step: float,
    origin: float = 0.0,
) -> bool:
    if (
        isinstance(step, bool)
        or not isinstance(step, (int, float))
        or not isfinite(float(step))
        or float(step) <= 0.0
    ):
        return False

    steps = (float(value) - float(origin)) / float(step)
    return isclose(steps, round(steps), rel_tol=0.0, abs_tol=1e-9)


def _normalize_price(value: float, symbol: SymbolInfo) -> float:
    tick_size = symbol.tick_size if symbol.tick_size > 0.0 else symbol.point
    if tick_size <= 0.0:
        raise ValueError("Symbol tick size must be greater than zero.")

    ticks = round(float(value) / float(tick_size))
    return round(ticks * float(tick_size), symbol.digits)


def _validate_price_relationships(
    *,
    side: OrderSide,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    minimum_stop_distance: float,
) -> tuple[bool, str]:
    if entry_price <= 0.0:
        return False, "Entry price must be greater than zero."

    minimum_distance = max(0.0, float(minimum_stop_distance))

    if side is OrderSide.BUY:
        if stop_loss >= entry_price:
            return False, "BUY stop loss must be below entry price."
        if take_profit <= entry_price:
            return False, "BUY take profit must be above entry price."
        stop_distance = entry_price - stop_loss
        target_distance = take_profit - entry_price
    elif side is OrderSide.SELL:
        if stop_loss <= entry_price:
            return False, "SELL stop loss must be above entry price."
        if take_profit >= entry_price:
            return False, "SELL take profit must be below entry price."
        stop_distance = stop_loss - entry_price
        target_distance = entry_price - take_profit
    else:
        return False, "Unsupported order side."

    if stop_distance < minimum_distance:
        return False, "Stop loss violates broker minimum stop distance."
    if target_distance < minimum_distance:
        return False, "Take profit violates broker minimum stop distance."

    return True, "Order validation successful."

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