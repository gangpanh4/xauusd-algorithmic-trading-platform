"""
Multi-timeframe market data loader.
"""

from __future__ import annotations

import MetaTrader5 as mt5

from core.trading_pipeline.market_context import MarketContext

from .history_loader import HistoryLoader


class MultiTimeframeLoader:
    """
    Loads synchronized market data across multiple timeframes.

    This class is responsible for building the MarketContext
    consumed by the Trading Pipeline and Intelligence Pipeline.
    """

    def __init__(self) -> None:
        self.loader = HistoryLoader()

    def load(
        self,
        symbol: str,
        bars: int,
    ) -> MarketContext:

        m5 = self.loader.load_history(
            symbol=symbol,
            timeframe=mt5.TIMEFRAME_M5,
            bars=bars,
        )

        m15 = self.loader.load_history(
            symbol=symbol,
            timeframe=mt5.TIMEFRAME_M15,
            bars=bars,
        )

        h1 = self.loader.load_history(
            symbol=symbol,
            timeframe=mt5.TIMEFRAME_H1,
            bars=bars,
        )

        h4 = self.loader.load_history(
            symbol=symbol,
            timeframe=mt5.TIMEFRAME_H4,
            bars=bars,
        )

        return MarketContext(
            current_bar=m15[-1],
            m5_bars=m5,
            m15_bars=m15,
            h1_bars=h1,
            h4_bars=h4,
        )