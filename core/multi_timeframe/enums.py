"""
Multi-Timeframe enumerations.
"""

from __future__ import annotations

from enum import Enum


class Timeframe(str, Enum):
    """
    Supported analysis timeframes.
    """

    WEEKLY = "W1"
    DAILY = "D1"
    H4 = "H4"
    H1 = "H1"
    M15 = "M15"
    M5 = "M5"


class TimeframeAlignment(str, Enum):
    """
    Alignment between higher and lower
    timeframe analyses.
    """

    ALIGNED = "aligned"

    PARTIAL = "partial"

    CONFLICT = "conflict"


class MarketBias(str, Enum):
    """
    High-level directional market bias.
    """

    BULLISH = "bullish"

    BEARISH = "bearish"

    NEUTRAL = "neutral"