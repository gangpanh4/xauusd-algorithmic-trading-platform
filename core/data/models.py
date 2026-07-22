"""
Core market data models.

This module contains lightweight immutable data models used
throughout the trading platform.

Only pure data structures belong here.
No MT5 logic or business logic should be placed in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class MarketBar:
    """
    Represents a single OHLCV market candle.

    This model is intentionally lightweight so it can be shared
    by the market data layer, market structure detectors,
    backtesting engine, and live trading pipeline.
    """

    timestamp: datetime

    open: float
    high: float
    low: float
    close: float

    tick_volume: int

    @property
    def body_size(
        self,
    ) -> float:
        """
        Absolute candle body size.
        """

        return abs(self.close - self.open)

    @property
    def range_size(
        self,
    ) -> float:
        """
        Total candle range.
        """

        return self.high - self.low

    @property
    def is_bullish(
        self,
    ) -> bool:
        """
        True if the candle closed above its open.
        """

        return self.close > self.open

    @property
    def is_bearish(
        self,
    ) -> bool:
        """
        True if the candle closed below its open.
        """

        return self.close < self.open

    @property
    def upper_wick(
        self,
    ) -> float:
        """
        Size of the upper wick.
        """

        return self.high - max(self.open, self.close)

    @property
    def lower_wick(
        self,
    ) -> float:
        """
        Size of the lower wick.
        """

        return min(self.open, self.close) - self.low

    @property
    def body_ratio(
        self,
    ) -> float:
        """
        Body size divided by total candle range.

        Returns 0.0 for zero-range candles.
        """

        if self.range_size <= 0.0:
            return 0.0

        return self.body_size / self.range_size