"""
Shared market context for the trading pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.regime_detector.models import MarketBar


@dataclass(slots=True)
class MarketContext:
    """
    Rolling market data supplied to the trading pipeline.
    """

    current_bar: MarketBar

    m5_bars: list[MarketBar]
    m15_bars: list[MarketBar]
    h1_bars: list[MarketBar]
    h4_bars: list[MarketBar]

    