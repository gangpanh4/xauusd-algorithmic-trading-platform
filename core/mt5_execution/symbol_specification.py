"""Broker symbol specification used by live risk calculations."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import MetaTrader5 as mt5


@dataclass(frozen=True, slots=True)
class LiveSymbolSpecification:
    """Validated broker economics for one tradable symbol."""

    symbol: str
    tick_size: float
    tick_value_per_lot: float
    lot_step: float
    minimum_lot: float
    maximum_lot: float
    minimum_stop_distance: float


def get_live_symbol_specification(symbol: str) -> LiveSymbolSpecification:
    """Read and validate risk-critical symbol metadata from MT5.

    ``tick_value_per_lot`` uses the loss-side tick value when the broker
    provides it, which is conservative for position-risk calculations.
    """

    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol must be a non-empty string")

    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(
            f"Unable to retrieve symbol information for {symbol}: "
            f"{mt5.last_error()}"
        )

    if not bool(getattr(info, "visible", False)):
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(
                f"Unable to select symbol {symbol}: {mt5.last_error()}"
            )
        info = mt5.symbol_info(symbol)
        if info is None:
            raise RuntimeError(
                f"Unable to refresh symbol information for {symbol}: "
                f"{mt5.last_error()}"
            )

    tick_size = _positive(
        getattr(info, "trade_tick_size", None),
        "trade_tick_size",
    )

    loss_tick_value = getattr(info, "trade_tick_value_loss", None)
    generic_tick_value = getattr(info, "trade_tick_value", None)
    tick_value_per_lot = _positive(
        loss_tick_value
        if _is_positive(loss_tick_value)
        else generic_tick_value,
        "trade_tick_value_loss/trade_tick_value",
    )

    lot_step = _positive(
        getattr(info, "volume_step", None),
        "volume_step",
    )
    minimum_lot = _positive(
        getattr(info, "volume_min", None),
        "volume_min",
    )
    maximum_lot = _positive(
        getattr(info, "volume_max", None),
        "volume_max",
    )
    if maximum_lot < minimum_lot:
        raise ValueError("volume_max cannot be smaller than volume_min")

    point = _positive(getattr(info, "point", None), "point")
    raw_stops_level = getattr(info, "trade_stops_level", 0)
    if isinstance(raw_stops_level, bool) or not isinstance(
        raw_stops_level,
        (int, float),
    ):
        raise TypeError("trade_stops_level must be numeric")
    stops_level = float(raw_stops_level)
    if not isfinite(stops_level) or stops_level < 0.0:
        raise ValueError("trade_stops_level must be finite and non-negative")

    minimum_stop_distance = max(
        tick_size,
        stops_level * point,
    )

    return LiveSymbolSpecification(
        symbol=symbol,
        tick_size=tick_size,
        tick_value_per_lot=tick_value_per_lot,
        lot_step=lot_step,
        minimum_lot=minimum_lot,
        maximum_lot=maximum_lot,
        minimum_stop_distance=minimum_stop_distance,
    )


def _is_positive(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and isfinite(float(value))
        and float(value) > 0.0
    )


def _positive(value: object, name: str) -> float:
    if not _is_positive(value):
        raise ValueError(f"{name} must be finite and greater than zero")
    return float(value)
