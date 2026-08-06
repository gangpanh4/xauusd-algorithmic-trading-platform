"""Validated MT5 order-history access for execution provenance."""

from __future__ import annotations

from datetime import UTC, datetime
from math import isfinite
from typing import Any

import MetaTrader5 as mt5

from .models import HistoricalOrderInfo, OrderSide


def get_historical_orders(
    *,
    date_from: datetime,
    date_to: datetime,
    symbol: str,
) -> list[HistoricalOrderInfo]:
    """Return authoritative order history for one exact symbol."""

    start = _aware_utc(date_from, "date_from")
    end = _aware_utc(date_to, "date_to")
    if end < start:
        raise ValueError("date_to must not be earlier than date_from")
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol must be a non-empty string")

    orders = mt5.history_orders_get(start, end, group=symbol)
    if orders is None:
        raise RuntimeError(
            f"Unable to retrieve MT5 order history: {mt5.last_error()}"
        )

    converted = [
        _to_historical_order(order)
        for order in orders
        if getattr(order, "symbol", None) == symbol
    ]
    converted.sort(key=lambda item: (item.completed_at, item.ticket))
    return converted


def _to_historical_order(raw: Any) -> HistoricalOrderInfo:
    return HistoricalOrderInfo(
        ticket=_positive_int(raw.ticket, "ticket"),
        symbol=_non_empty_string(raw.symbol, "symbol"),
        side=_order_side(raw.type),
        volume_initial=_non_negative_float(
            raw.volume_initial,
            "volume_initial",
        ),
        volume_current=_non_negative_float(
            raw.volume_current,
            "volume_current",
        ),
        price_open=_non_negative_float(
            raw.price_open,
            "price_open",
        ),
        stop_loss=_non_negative_float(getattr(raw, "sl", 0.0), "sl"),
        take_profit=_non_negative_float(getattr(raw, "tp", 0.0), "tp"),
        magic_number=_non_negative_int(getattr(raw, "magic", 0), "magic"),
        comment=str(getattr(raw, "comment", "")),
        created_at=_timestamp(raw, "time_setup_msc", "time_setup"),
        completed_at=_timestamp(raw, "time_done_msc", "time_done"),
        state=int(raw.state),
    )


def _order_side(value: object) -> OrderSide:
    if value == mt5.ORDER_TYPE_BUY:
        return OrderSide.BUY
    if value == mt5.ORDER_TYPE_SELL:
        return OrderSide.SELL
    raise ValueError(f"Unsupported historical-order type: {value!r}")


def _timestamp(raw: Any, msc_name: str, seconds_name: str) -> datetime:
    milliseconds = getattr(raw, msc_name, None)
    if (
        isinstance(milliseconds, (int, float))
        and not isinstance(milliseconds, bool)
        and isfinite(float(milliseconds))
        and float(milliseconds) > 0.0
    ):
        return datetime.fromtimestamp(float(milliseconds) / 1000.0, tz=UTC)

    seconds = getattr(raw, seconds_name, None)
    if (
        isinstance(seconds, (int, float))
        and not isinstance(seconds, bool)
        and isfinite(float(seconds))
        and float(seconds) > 0.0
    ):
        return datetime.fromtimestamp(float(seconds), tz=UTC)

    raise ValueError("Historical-order timestamp is invalid.")


def _aware_utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _non_empty_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _positive_int(value: object, name: str) -> int:
    numeric = _non_negative_int(value, name)
    if numeric == 0:
        raise ValueError(f"{name} must be greater than zero")
    return numeric


def _non_negative_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} cannot be negative")
    return value


def _non_negative_float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    numeric = float(value)
    if not isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    if numeric < 0.0:
        raise ValueError(f"{name} cannot be negative")
    return numeric
