"""
Configuration for the Fair Value Gap detector.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(
    slots=True,
    frozen=True,
)
class FairValueGapDetectorConfig:
    """
    Configuration controlling Fair Value Gap detection.

    Version 1 uses simple price-gap rules.
    Future versions will introduce ATR-,
    volatility-, and session-aware filtering.
    """

    # Minimum size of the gap in price units.
    minimum_gap_size: float = 0.20

    # Ignore tiny candle bodies.
    minimum_body_size: float = 0.10

    # Require the middle candle to have a
    # meaningful body relative to its range.
    minimum_body_ratio: float = 0.50

    # Maximum number of historical bars
    # examined during one detection cycle.
    lookback_bars: int = 300

    # Enable additional debug logging.
    debug_logging: bool = False