"""Read-only MT5 quote access within an already-owned terminal session."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import isfinite

import MetaTrader5 as mt5  # type: ignore[import-untyped]


@dataclass(frozen=True, slots=True)
class MarketQuote:
    """One validated top-of-book quote normalized to actual UTC."""

    symbol: str
    timestamp_utc: datetime
    bid: float
    ask: float

    def __post_init__(self) -> None:
        symbol = self.symbol.strip().upper()
        if not symbol:
            raise ValueError("symbol must be non-empty")
        timestamp = self.timestamp_utc
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("timestamp_utc must be timezone-aware")
        if isinstance(self.bid, bool) or isinstance(self.ask, bool):
            raise TypeError("bid and ask must be numeric")
        bid = float(self.bid)
        ask = float(self.ask)
        if not isfinite(bid) or not isfinite(ask):
            raise ValueError("bid and ask must be finite")
        if bid <= 0.0 or ask <= 0.0:
            raise ValueError("bid and ask must be greater than zero")
        if ask < bid:
            raise ValueError("ask cannot be less than bid")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "timestamp_utc", timestamp.astimezone(UTC))
        object.__setattr__(self, "bid", bid)
        object.__setattr__(self, "ask", ask)

    @property
    def mid(self) -> float:
        """Return the arithmetic midpoint of bid and ask."""

        return (self.bid + self.ask) / 2.0

    @property
    def spread_price(self) -> float:
        """Return the quote spread in price units."""

        return self.ask - self.bid


class QuoteReader:
    """Read one MT5 quote without owning or mutating the MT5 session."""

    def __init__(self, symbol: str, *, server_utc_offset_hours: float = 0.0) -> None:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must be non-empty")
        if isinstance(server_utc_offset_hours, bool):
            raise TypeError("server_utc_offset_hours must be numeric")
        offset = float(server_utc_offset_hours)
        if not isfinite(offset):
            raise ValueError("server_utc_offset_hours must be finite")
        self.symbol = normalized_symbol
        self.server_utc_offset_hours = offset

    def read(self) -> MarketQuote:
        """Return the current validated quote from the active MT5 session."""

        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            raise RuntimeError(
                f"Unable to retrieve latest tick for {self.symbol}: {mt5.last_error()}"
            )
        try:
            raw_timestamp = tick.time
            raw_bid = tick.bid
            raw_ask = tick.ask
        except AttributeError as exc:
            raise RuntimeError(
                f"Latest tick for {self.symbol} is missing a required field."
            ) from exc

        timestamp = self._normalize_timestamp(raw_timestamp)
        try:
            bid = float(raw_bid)
            ask = float(raw_ask)
        except (TypeError, ValueError) as exc:
            raise TypeError("MT5 bid and ask must be numeric") from exc

        return MarketQuote(
            symbol=self.symbol,
            timestamp_utc=timestamp,
            bid=bid,
            ask=ask,
        )

    def _normalize_timestamp(self, raw_timestamp: float) -> datetime:
        """Apply the same explicit broker-offset semantics as MarketDataService."""

        if isinstance(raw_timestamp, bool):
            raise TypeError("MT5 timestamp must be numeric")
        try:
            raw_value = float(raw_timestamp)
        except (TypeError, ValueError) as exc:
            raise TypeError("MT5 timestamp must be numeric") from exc
        if not isfinite(raw_value):
            raise ValueError("MT5 timestamp must be finite")
        broker_encoded = datetime.fromtimestamp(raw_value, tz=UTC)
        return broker_encoded - timedelta(hours=self.server_utc_offset_hours)
