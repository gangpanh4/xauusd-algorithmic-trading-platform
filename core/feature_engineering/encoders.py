"""
Feature encoders.

Utility functions for converting categorical
domain values into numerical feature values.
"""

from __future__ import annotations

from core.market_structure.enums import (
    MarketTrend,
)


def encode_trend(
    trend: MarketTrend,
) -> float:
    """
    Encode market trend into a numerical feature.

    Returns:
        +1.0 -> Bullish
         0.0 -> Unknown
        -1.0 -> Bearish
    """

    mapping = {
        MarketTrend.BULLISH: 1.0,
        MarketTrend.BEARISH: -1.0,
        MarketTrend.UNKNOWN: 0.0,
    }

    return mapping[trend]