"""Validated MT5 deal-history access for live reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from typing import Any

import MetaTrader5 as mt5

from .models import ExecutionDealInfo, OrderSide


@dataclass(frozen=True, slots=True)
class RealizedDeal:
    """One broker deal that realizes account-currency P&L."""

    ticket: int
    position_id: int
    timestamp: datetime
    symbol: str
    entry: int
    profit: float
    commission: float
    swap: float
    fee: float

    @property
    def net_pnl(self) -> float:
        return self.profit + self.commission + self.swap + self.fee


_CLOSING_ENTRIES = frozenset(
    value
    for value in (
        getattr(mt5, "DEAL_ENTRY_OUT", None),
        getattr(mt5, "DEAL_ENTRY_INOUT", None),
        getattr(mt5, "DEAL_ENTRY_OUT_BY", None),
    )
    if value is not None
)


def get_execution_deals(
    *,
    date_from: datetime,
    date_to: datetime,
    symbol: str,
) -> list[ExecutionDealInfo]:
    """Return all authoritative execution deals for one symbol."""

    start, end = _validated_range(date_from, date_to, symbol)
    deals = mt5.history_deals_get(start, end, group=symbol)
    if deals is None:
        raise RuntimeError(
            f"Unable to retrieve MT5 deal history: {mt5.last_error()}"
        )

    converted = [
        _to_execution_deal(raw)
        for raw in deals
        if getattr(raw, "symbol", None) == symbol
    ]
    converted.sort(key=lambda item: (item.timestamp, item.ticket))
    return converted


def get_realized_deals(
    *,
    date_from: datetime,
    date_to: datetime,
    symbol: str,
) -> list[RealizedDeal]:
    """Return closing and reversal deals for one symbol."""

    start, end = _validated_range(date_from, date_to, symbol)
    deals = mt5.history_deals_get(start, end, group=symbol)
    if deals is None:
        raise RuntimeError(
            f"Unable to retrieve MT5 deal history: {mt5.last_error()}"
        )

    realized: list[RealizedDeal] = []
    for raw in deals:
        if getattr(raw, "symbol", None) != symbol:
            continue
        entry = int(raw.entry)
        if entry not in _CLOSING_ENTRIES:
            continue
        realized.append(_to_realized_deal(raw))

    realized.sort(key=lambda item: (item.timestamp, item.ticket))
    return realized


def _to_execution_deal(raw: Any) -> ExecutionDealInfo:
    return ExecutionDealInfo(
        ticket=_positive_int(raw.ticket, "ticket"),
        order_ticket=_positive_int(raw.order, "order"),
        position_id=_non_negative_int(
            getattr(raw, "position_id", 0),
            "position_id",
        ),
        timestamp=_deal_timestamp(raw),
        symbol=_non_empty_string(raw.symbol, "symbol"),
        side=_deal_side(raw.type),
        volume=_positive_float(raw.volume, "volume"),
        price=_non_negative_float(raw.price, "price"),
        entry=int(raw.entry),
        magic_number=_non_negative_int(getattr(raw, "magic", 0), "magic"),
        comment=str(getattr(raw, "comment", "")),
    )


def _to_realized_deal(raw: Any) -> RealizedDeal:
    symbol = _non_empty_string(getattr(raw, "symbol", None), "symbol")
    return RealizedDeal(
        ticket=_positive_int(raw.ticket, "ticket"),
        position_id=_non_negative_int(
            getattr(raw, "position_id", 0),
            "position_id",
        ),
        timestamp=_deal_timestamp(raw),
        symbol=symbol,
        entry=int(raw.entry),
        profit=_finite(getattr(raw, "profit", 0.0), "profit"),
        commission=_finite(
            getattr(raw, "commission", 0.0),
            "commission",
        ),
        swap=_finite(getattr(raw, "swap", 0.0), "swap"),
        fee=_finite(getattr(raw, "fee", 0.0), "fee"),
    )


def _validated_range(
    date_from: datetime,
    date_to: datetime,
    symbol: str,
) -> tuple[datetime, datetime]:
    start = _aware_utc(date_from, "date_from")
    end = _aware_utc(date_to, "date_to")
    if end < start:
        raise ValueError("date_to must not be earlier than date_from")
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol must be a non-empty string")
    return start, end


def _deal_side(value: object) -> OrderSide:
    if value == mt5.DEAL_TYPE_BUY:
        return OrderSide.BUY
    if value == mt5.DEAL_TYPE_SELL:
        return OrderSide.SELL
    raise ValueError(f"Unsupported execution-deal type: {value!r}")


def _deal_timestamp(raw: Any) -> datetime:
    time_msc = getattr(raw, "time_msc", None)
    if isinstance(time_msc, (int, float)) and not isinstance(time_msc, bool):
        numeric = float(time_msc)
        if isfinite(numeric) and numeric > 0.0:
            return datetime.fromtimestamp(numeric / 1000.0, tz=UTC)

    seconds = _finite(raw.time, "time")
    if seconds <= 0.0:
        raise ValueError("deal time must be greater than zero")
    return datetime.fromtimestamp(seconds, tz=UTC)


def _aware_utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    numeric = float(value)
    if not isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


def _positive_float(value: object, name: str) -> float:
    numeric = _non_negative_float(value, name)
    if numeric == 0.0:
        raise ValueError(f"{name} must be greater than zero")
    return numeric


def _non_negative_float(value: object, name: str) -> float:
    numeric = _finite(value, name)
    if numeric < 0.0:
        raise ValueError(f"{name} cannot be negative")
    return numeric


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


def _non_empty_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value
