"""
MT5 Symbol information.
"""

from __future__ import annotations

import MetaTrader5 as mt5

from .models import SymbolInfo


def get_symbol_info(
    symbol: str,
) -> SymbolInfo:
    """
    Retrieve MT5 symbol information.
    """

    info = mt5.symbol_info(symbol)

    if info is None:
        raise RuntimeError(
            f"Unable to retrieve symbol: {symbol}"
        )

    return SymbolInfo(
        name=info.name,
        digits=info.digits,
        point=info.point,
        spread=info.spread,
        volume_min=info.volume_min,
        volume_max=info.volume_max,
        volume_step=info.volume_step,
        trade_allowed=info.trade_mode != 0,
        tick_size=float(
            getattr(info, "trade_tick_size", 0.0)
            or getattr(info, "point", 0.0)
        ),
        minimum_stop_distance=max(
            float(
                getattr(info, "trade_tick_size", 0.0)
                or getattr(info, "point", 0.0)
            ),
            float(getattr(info, "trade_stops_level", 0.0))
            * float(getattr(info, "point", 0.0)),
        ),
        filling_mode_flags=int(getattr(info, "filling_mode", 0)),
        trade_execution_mode=int(
            getattr(info, "trade_exemode", -1)
        ),
    )