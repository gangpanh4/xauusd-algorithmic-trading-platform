"""
Market Structure Detector Result

Defines the immutable output produced by a single detector.

Author: Trading Intelligence Platform
"""

from __future__ import annotations

from dataclasses import dataclass

from .events import MarketEvent
from .measurement_models import Measurement
from .zones import PriceZone


@dataclass(frozen=True, slots=True)
class DetectorResult:
    """
    Immutable output of a single Market Structure detector.
    """

    events: tuple[MarketEvent, ...] = ()

    zones: tuple[PriceZone, ...] = ()

    measurements: tuple[Measurement, ...] = ()