"""
Live Market Data Service.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import isfinite
from typing import Any

import MetaTrader5 as mt5

from core.data.models import (
    MarketBar,
)


class MarketDataService:
    """
    Retrieves completed candles from MT5.

    The service guarantees that each completed candle is
    returned only once.
    """

    def __init__(
        self,
        symbol: str,
        timeframe: int,
        *,
        server_utc_offset_hours: float = 0.0,
        max_clock_skew_seconds: float = 120.0,
    ) -> None:

        if not isfinite(server_utc_offset_hours):
            raise ValueError(
                "server_utc_offset_hours must be finite."
            )
        if (
            not isfinite(max_clock_skew_seconds)
            or max_clock_skew_seconds < 0.0
        ):
            raise ValueError(
                "max_clock_skew_seconds must be finite and non-negative."
            )

        self.symbol = symbol
        self.timeframe = timeframe
        self.server_utc_offset_hours = server_utc_offset_hours
        self.max_clock_skew_seconds = max_clock_skew_seconds

        self._last_bar_time: datetime | None = None

    def get_latest_closed_bar(
        self,
    ) -> MarketBar | None:
        """
        Return the latest completed candle.

        Returns None if no new completed candle exists.
        """

        rates = mt5.copy_rates_from_pos(
            self.symbol,
            self.timeframe,
            1,      # skip current forming candle
            1,
        )

        if rates is None:
            raise RuntimeError(
                f"Unable to retrieve latest closed bar for "
                f"{self.symbol}: {mt5.last_error()}"
            )

        if len(rates) == 0:
            return None

        rate: Any = rates[0]

        timestamp = self._normalize_timestamp(
            rate["time"],
        )

        if self._last_bar_time == timestamp:
            return None

        self._last_bar_time = timestamp

        return MarketBar(
            timestamp=timestamp,
            open=rate["open"],
            high=rate["high"],
            low=rate["low"],
            close=rate["close"],
            tick_volume=rate["tick_volume"],
        )

    def get_historical_bars(
        self,
        count: int,
    ) -> list[MarketBar]:
        """
        Return the latest completed historical bars.
        """

        rates = mt5.copy_rates_from_pos(
            self.symbol,
            self.timeframe,
            1,          # skip the currently forming candle
            count,
        )

        if rates is None:
            raise RuntimeError(
                f"Unable to retrieve historical bars for "
                f"{self.symbol}: {mt5.last_error()}"
            )

        bars: list[MarketBar] = []
        previous_timestamp: datetime | None = None

        # MT5 returns copied rates oldest-to-newest. Preserve that order for
        # downstream completed-bar consumers.
        for rate in rates:
            timestamp = self._normalize_timestamp(
                rate["time"],
            )

            if (
                previous_timestamp is not None
                and timestamp <= previous_timestamp
            ):
                raise RuntimeError(
                    "Historical MT5 bars must be strictly increasing "
                    "without duplicate timestamps."
                )

            bars.append(
                MarketBar(
                    timestamp=timestamp,
                    open=rate["open"],
                    high=rate["high"],
                    low=rate["low"],
                    close=rate["close"],
                    tick_volume=rate["tick_volume"],
                )
            )
            previous_timestamp = timestamp

        return bars

    def validate_clock_alignment(
        self,
        *,
        reference_utc: datetime | None = None,
    ) -> datetime:
        """Validate normalized MT5 tick time against authoritative UTC.

        The method does not infer or mutate the configured server offset.
        A wrong offset fails closed before warm-up or live analysis proceeds.
        """

        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            raise RuntimeError(
                f"Unable to retrieve latest tick for {self.symbol}: "
                f"{mt5.last_error()}"
            )

        raw_time = getattr(tick, "time", None)
        if raw_time is None:
            raise RuntimeError(
                f"Latest tick for {self.symbol} has no timestamp."
            )

        normalized = self._normalize_timestamp(raw_time)
        now = datetime.now(UTC) if reference_utc is None else reference_utc
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("reference_utc must be timezone-aware.")
        now_utc = now.astimezone(UTC)

        skew_seconds = abs(
            (normalized - now_utc).total_seconds()
        )
        if skew_seconds > self.max_clock_skew_seconds:
            raise RuntimeError(
                "Normalized MT5 clock is outside the allowed UTC skew: "
                f"symbol={self.symbol} "
                f"normalized={normalized.isoformat()} "
                f"system_utc={now_utc.isoformat()} "
                f"skew_seconds={skew_seconds:.3f} "
                f"allowed_seconds={self.max_clock_skew_seconds:.3f} "
                f"configured_server_offset_hours="
                f"{self.server_utc_offset_hours}."
            )

        return normalized

    def _normalize_timestamp(
        self,
        raw_timestamp: Any,
    ) -> datetime:
        """Convert one broker-encoded Unix timestamp to actual UTC."""

        if isinstance(raw_timestamp, bool):
            raise TypeError("MT5 timestamp must be numeric.")
        try:
            raw_value = float(raw_timestamp)
        except (TypeError, ValueError) as exc:
            raise TypeError("MT5 timestamp must be numeric.") from exc
        if not isfinite(raw_value):
            raise ValueError("MT5 timestamp must be finite.")

        broker_encoded = datetime.fromtimestamp(raw_value, tz=UTC)
        return broker_encoded - timedelta(
            hours=self.server_utc_offset_hours
        )
