"""
Shared data models for the Market Structure Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.market_structure.enums import (
    BreakType,
    SwingType,
)

@dataclass(slots=True, frozen=True)
class SwingPoint:
    """
    Immutable representation of a confirmed market swing.

    SwingPoint objects are produced exclusively by the SwingDetector
    and consumed by downstream market structure detectors.
    """

    timestamp: datetime
    index: int
    price: float
    swing_type: SwingType

    # Index of the candle where this swing became confirmed.
    confirmation_index: int

@dataclass(slots=True, frozen=True)
class BOSEvent:
    """
    Immutable representation of a confirmed Break of Structure (BOS).

    BOSEvent objects are produced exclusively by the BOSDetector
    and consumed by downstream market structure components.
    """

    timestamp: datetime

    # Type of structural break.
    break_type: BreakType

    # Swing that was broken.
    swing_point: SwingPoint

    # Index of the candle where this BOS became confirmed.
    confirmation_index: int