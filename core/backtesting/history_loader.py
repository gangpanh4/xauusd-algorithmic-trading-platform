"""
Historical market data loader.
"""

from __future__ import annotations

from datetime import UTC, datetime

import MetaTrader5 as mt5

from core.regime_detector.models import MarketBar


class HistoryLoader:
    """
    Loads historical market data from MT5.
    """

    def load_history(
        self,
        symbol: str,
        timeframe: int,
        bars: int,
    ) -> list[MarketBar]:
        """
        Load historical bars from MT5.
        """

        rates = mt5.copy_rates_from_pos(
            symbol,
            timeframe,
            0,
            bars,
        )

        if rates is None:
            error = mt5.last_error()
            raise RuntimeError(
                f"Unable to load history: {error}"
            )

        history: list[MarketBar] = []

        for rate in rates:
            history.append(
                MarketBar(
                    timestamp=datetime.fromtimestamp(
                        rate["time"],
                        UTC,
                    ),
                    open=float(rate["open"]),
                    high=float(rate["high"]),
                    low=float(rate["low"]),
                    close=float(rate["close"]),
                    volume=float(rate["tick_volume"]),
                    spread=float(rate["spread"]),
                    tick_volume=int(rate["tick_volume"]),
                    real_volume=int(rate["real_volume"]),
                )
            )

        return history