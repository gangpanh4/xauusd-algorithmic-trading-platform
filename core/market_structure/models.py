"""
Shared data models for the Market Structure Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.market_structure.enums import SwingType


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