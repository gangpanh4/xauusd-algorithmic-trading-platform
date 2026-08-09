"""Pure broker-independent price normalization and recentering helpers."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class PriceGeometry:
    """Approved price distances recentered on one execution reference."""

    reference_entry_price: float
    stop_loss: float
    take_profit: float
    stop_distance: float
    target_distance: float
    normalized_to_tick: bool


def normalize_price_to_tick(
    value: float,
    *,
    tick_size: float,
    digits: int | None = None,
) -> float:
    """Round a positive price to the nearest tick using MT5 semantics."""

    price = _positive(value, "value")
    tick = _positive(tick_size, "tick_size")
    if digits is not None:
        if isinstance(digits, bool) or not isinstance(digits, int):
            raise TypeError("digits must be an integer or None")
        if digits < 0:
            raise ValueError("digits cannot be negative")

    normalized = round(price / tick) * tick
    return round(normalized, digits) if digits is not None else normalized


def recenter_exit_levels(
    *,
    is_buy: bool,
    planned_entry_price: float,
    planned_stop_loss: float,
    planned_take_profit: float,
    reference_entry_price: float,
    normalize_to_tick: bool = False,
    tick_size: float | None = None,
    digits: int | None = None,
) -> PriceGeometry:
    """Preserve approved distances around a new reference entry price.

    When ``normalize_to_tick`` is false, this is the current historical
    simulator behavior. When true, the entry is normalized first and the
    recentered protective levels are then normalized, matching the pure
    price-construction semantics used by the live request builder.
    """

    if not isinstance(is_buy, bool):
        raise TypeError("is_buy must be a bool")
    if not isinstance(normalize_to_tick, bool):
        raise TypeError("normalize_to_tick must be a bool")

    planned_entry = _positive(planned_entry_price, "planned_entry_price")
    planned_stop = _positive(planned_stop_loss, "planned_stop_loss")
    planned_target = _positive(
        planned_take_profit,
        "planned_take_profit",
    )
    reference_entry = _positive(
        reference_entry_price,
        "reference_entry_price",
    )

    if is_buy:
        if not planned_stop < planned_entry < planned_target:
            raise ValueError(
                "BUY geometry requires stop < entry < target"
            )
        stop_distance = planned_entry - planned_stop
        target_distance = planned_target - planned_entry
    else:
        if not planned_target < planned_entry < planned_stop:
            raise ValueError(
                "SELL geometry requires target < entry < stop"
            )
        stop_distance = planned_stop - planned_entry
        target_distance = planned_entry - planned_target

    if normalize_to_tick:
        if tick_size is None:
            raise ValueError(
                "tick_size is required when normalize_to_tick is true"
            )
        entry = normalize_price_to_tick(
            reference_entry,
            tick_size=tick_size,
            digits=digits,
        )
    else:
        entry = reference_entry

    stop_loss = entry - stop_distance if is_buy else entry + stop_distance
    take_profit = entry + target_distance if is_buy else entry - target_distance

    if normalize_to_tick:
        stop_loss = normalize_price_to_tick(
            stop_loss,
            tick_size=tick_size,
            digits=digits,
        )
        take_profit = normalize_price_to_tick(
            take_profit,
            tick_size=tick_size,
            digits=digits,
        )

    return PriceGeometry(
        reference_entry_price=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        stop_distance=stop_distance,
        target_distance=target_distance,
        normalized_to_tick=normalize_to_tick,
    )


def _positive(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    converted = float(value)
    if not isfinite(converted) or converted <= 0.0:
        raise ValueError(f"{name} must be finite and greater than zero")
    return converted
