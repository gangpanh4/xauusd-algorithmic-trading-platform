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

    # Structure confidence scoring
    swing_confidence_weight: float = 0.20
    bos_confidence_weight: float = 0.35
    choch_confidence_weight: float = 0.20
    liquidity_confidence_weight: float = 0.25

    @property
    def maximum_confidence_score(self) -> float:
        """
        Maximum achievable structure confidence.
        """

        return (
            self.swing_confidence_weight
            + self.bos_confidence_weight
            + self.choch_confidence_weight
            + self.liquidity_confidence_weight
        )


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


@dataclass(slots=True, frozen=True)
class CHOCHDetectorConfig:
    """
    Immutable configuration for the Change of Character (CHoCH) Detector.
    """

    # Minimum price movement required to confirm a CHoCH.
    minimum_break_distance: float = 0.0

    # Maximum number of confirmed swings retained.
    maximum_history: int = 5000

    # Enable diagnostic logging.
    debug_logging: bool = False


MarketStructureCHOCHConfig = CHOCHDetectorConfig


@dataclass(slots=True)
class LiquidityDetectorConfig:
    """
    Configuration for the Liquidity Sweep Detector.

    Controls minimum distance and validation rules
    for liquidity sweeps.
    """

    # Minimum price distance required to consider a sweep valid.
    minimum_sweep_distance: float = 0.0

    # Allow equal highs/lows to form liquidity pools.
    allow_equal_levels: bool = True