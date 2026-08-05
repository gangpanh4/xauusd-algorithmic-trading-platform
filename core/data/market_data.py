"""
Live Market Data Service.
"""

from __future__ import annotations

from datetime import UTC, datetime
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
    ) -> None:

        self.symbol = symbol
        self.timeframe = timeframe

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

        timestamp = datetime.fromtimestamp(
            rate["time"],
            tz=UTC,
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
            timestamp = datetime.fromtimestamp(
                rate["time"],
                tz=UTC,
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