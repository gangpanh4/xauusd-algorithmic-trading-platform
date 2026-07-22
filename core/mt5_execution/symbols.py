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
    )