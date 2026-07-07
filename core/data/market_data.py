"""
Live Market Data Service.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import MetaTrader5 as mt5


@dataclass(frozen=True)
class MarketBar:
    """
    Normalized market bar used by the live trading engine.
    """

    timestamp: datetime

    open: float
    high: float
    low: float
    close: float

    tick_volume: int


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

        if rates is None or len(rates) == 0:
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
            return []

        bars: list[MarketBar] = []

        for rate in reversed(rates):

            bars.append(
                MarketBar(
                    timestamp=datetime.fromtimestamp(
                        rate["time"],
                        tz=UTC,
                    ),
                    open=rate["open"],
                    high=rate["high"],
                    low=rate["low"],
                    close=rate["close"],
                    tick_volume=rate["tick_volume"],
                )
            )

        return bars