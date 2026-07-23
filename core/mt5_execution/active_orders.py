"""MT5 active-order reconciliation."""

from __future__ import annotations

import MetaTrader5 as mt5


def get_active_order_count(symbol: str) -> int:
    """Return the authoritative number of active broker orders for a symbol."""

    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol must be a non-empty string")

    orders = mt5.orders_get(symbol=symbol)
    if orders is None:
        raise RuntimeError(
            f"Unable to retrieve active MT5 orders: {mt5.last_error()}"
        )

    return len(orders)
