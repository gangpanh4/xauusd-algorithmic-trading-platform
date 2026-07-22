"""Validated MT5 deal-history access for live risk reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from typing import Any

import MetaTrader5 as mt5


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


def get_realized_deals(
    *,
    date_from: datetime,
    date_to: datetime,
    symbol: str,
) -> list[RealizedDeal]:
    """Return closing and reversal deals for one symbol."""

    start = _aware_utc(date_from, "date_from")
    end = _aware_utc(date_to, "date_to")
    if end < start:
        raise ValueError("date_to must not be earlier than date_from")
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol must be a non-empty string")

    deals = mt5.history_deals_get(start, end, group=symbol)
    if deals is None:
        raise RuntimeError(
            f"Unable to retrieve MT5 deal history: {mt5.last_error()}"
        )

    realized: list[RealizedDeal] = []
    for raw in deals:
        if getattr(raw, "symbol", None) != symbol:
            continue
        entry = int(getattr(raw, "entry"))
        if entry not in _CLOSING_ENTRIES:
            continue
        realized.append(_to_realized_deal(raw))

    realized.sort(key=lambda item: (item.timestamp, item.ticket))
    return realized


def _to_realized_deal(raw: Any) -> RealizedDeal:
    time_msc = getattr(raw, "time_msc", None)
    if isinstance(time_msc, (int, float)) and not isinstance(time_msc, bool):
        timestamp = datetime.fromtimestamp(float(time_msc) / 1000.0, tz=UTC)
    else:
        timestamp = datetime.fromtimestamp(float(getattr(raw, "time")), tz=UTC)

    symbol = getattr(raw, "symbol", None)
    if not isinstance(symbol, str) or not symbol:
        raise ValueError("deal symbol must be a non-empty string")

    return RealizedDeal(
        ticket=_positive_int(getattr(raw, "ticket"), "ticket"),
        position_id=_non_negative_int(
            getattr(raw, "position_id", 0),
            "position_id",
        ),
        timestamp=timestamp,
        symbol=symbol,
        entry=int(getattr(raw, "entry")),
        profit=_finite(getattr(raw, "profit", 0.0), "profit"),
        commission=_finite(
            getattr(raw, "commission", 0.0),
            "commission",
        ),
        swap=_finite(getattr(raw, "swap", 0.0), "swap"),
        fee=_finite(getattr(raw, "fee", 0.0), "fee"),
    )


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
