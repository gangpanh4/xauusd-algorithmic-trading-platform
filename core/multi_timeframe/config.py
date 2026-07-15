"""
Multi-Timeframe configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .enums import Timeframe


@dataclass(slots=True, frozen=True)
class MultiTimeframeConfig:
    """
    Configuration for the Multi-Timeframe Engine.
    """

    # -------------------------------------------------
    # Active Timeframes
    # -------------------------------------------------

    active_timeframes: tuple[Timeframe, ...] = (
        Timeframe.WEEKLY,
        Timeframe.DAILY,
        Timeframe.H4,
        Timeframe.H1,
        Timeframe.M15,
        Timeframe.M5,
    )

    # -------------------------------------------------
    # Hierarchy
    # Highest authority → Lowest authority
    # -------------------------------------------------

    hierarchy: tuple[Timeframe, ...] = (
        Timeframe.WEEKLY,
        Timeframe.DAILY,
        Timeframe.H4,
        Timeframe.H1,
        Timeframe.M15,
        Timeframe.M5,
    )

    # -------------------------------------------------
    # Authority Weights
    # Used by Confluence / Decision Engine
    # -------------------------------------------------

    timeframe_weights: dict[Timeframe, float] = field(
        default_factory=lambda: {
            Timeframe.WEEKLY: 0.30,
            Timeframe.DAILY: 0.25,
            Timeframe.H4: 0.20,
            Timeframe.H1: 0.15,
            Timeframe.M15: 0.07,
            Timeframe.M5: 0.03,
        }
    )

    # -------------------------------------------------
    # Confidence
    # -------------------------------------------------

    minimum_confidence: float = 0.60

    alignment_threshold: float = 0.75

    # -------------------------------------------------
    # Execution
    # -------------------------------------------------

    use_execution_refinement: bool = True

    execution_timeframe: Timeframe = Timeframe.M5

    entry_timeframe: Timeframe = Timeframe.M15

    # -------------------------------------------------
    # Debug
    # -------------------------------------------------

    debug_logging: bool = False