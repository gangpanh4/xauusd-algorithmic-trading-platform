"""
Configuration for the Swing Detection Engine.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class SwingDetectorConfig:
    """
    Immutable configuration for the Swing Detection Engine.

    All parameters influence detector behavior without embedding
    magic numbers or algorithm-specific constants in the implementation.
    """

    # Pivot confirmation
    pivot_left: int = 3
    pivot_right: int = 3

    # Swing validation
    minimum_swing_distance: float = 0.0

    # Equal high / low handling
    equal_high_tolerance: float = 0.0
    equal_low_tolerance: float = 0.0

    # ATR validation
    atr_validation: bool = True
    atr_period: int = 14
    atr_multiplier: float = 1.0

    # Runtime limits
    maximum_history: int = 5000

    # Diagnostics
    debug_logging: bool = False


MarketStructureConfig = SwingDetectorConfig

@dataclass(slots=True, frozen=True)
class BOSDetectorConfig:
    """
    Immutable configuration for the Break of Structure (BOS) Detector.

    These parameters control how confirmed structural breaks
    are identified from previously confirmed SwingPoint objects.
    """

    # Require the candle to CLOSE beyond the swing level.
    require_close_break: bool = True

    # Allow wick-only breaks to count as BOS.
    allow_wick_break: bool = False

    # Minimum price distance beyond the swing level.
    minimum_break_distance: float = 0.0

    # Tolerance for equal highs/lows when evaluating breaks.
    break_tolerance: float = 0.0

    # Diagnostics
    debug_logging: bool = False