"""
Historical market data loader.
"""

from __future__ import annotations

from datetime import UTC, datetime

import MetaTrader5 as mt5

from core.regime_detector.models import MarketBar


class HistoryLoader:
    """
    Loads and validates historical market data.
    """

    def load_history(
        self,
        symbol: str,
        timeframe: int,
        bars: int,
    ) -> list[MarketBar]:

        rates = mt5.copy_rates_from_pos(
            symbol,
            timeframe,
            0,
            bars,
        )

        if rates is None:
            raise RuntimeError(
                f"Unable to load history: {mt5.last_error()}"
            )

        history: list[MarketBar] = []

        seen = set()

        for rate in rates:

            timestamp = datetime.fromtimestamp(
                rate["time"],
                UTC,
            )

            # Skip duplicated timestamps
            if timestamp in seen:
                continue

            seen.add(timestamp)

            # Ignore invalid candles
            if (
                rate["high"] < rate["low"]
                or rate["open"] <= 0
                or rate["close"] <= 0
            ):
                continue

            history.append(
                MarketBar(
                    timestamp=timestamp,
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

        # Ensure chronological order
        history.sort(
            key=lambda bar: bar.timestamp,
        )

        if len(history) < 2:
            raise RuntimeError(
                "Insufficient historical data."
            )

        # Detect abnormal time gaps
        gaps = 0

        for previous, current in zip(
            history,
            history[1:],
        ):

            delta = (
                current.timestamp
                - previous.timestamp
            ).total_seconds()

            if delta <= 0:
                raise RuntimeError(
                    "History timestamps are not strictly increasing."
                )

            # Gap larger than one day
            if delta > 86400:
                gaps += 1

        if gaps:
            print(
                f"[HistoryLoader] Warning: detected {gaps} large historical gaps."
            )

        return history