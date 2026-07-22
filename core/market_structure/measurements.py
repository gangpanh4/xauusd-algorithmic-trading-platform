"""
Market structure quantitative measurements.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MarketStructureMeasurements:
    """
    Quantitative measurements derived from market structure.
    """

    bos_distance: float = 0.0
    bos_age: int = 0

    choch_distance: float = 0.0
    choch_age: int = 0

    liquidity_distance: float = 0.0
    liquidity_age: int = 0

    swing_distance: float = 0.0
    swing_age: int = 0