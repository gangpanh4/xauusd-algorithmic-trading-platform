"""
Market Structure Processing Context

This module defines the immutable processing context shared between
Market Structure detectors.

The context represents the complete published market structure state
available while processing a single completed MarketBar.

Author: Trading Intelligence Platform
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core.data.models import MarketBar

from .events import MarketEvent
from .measurement_models import Measurement
from .zones import PriceZone


# ============================================================================
# Processing Metadata
# ============================================================================


@dataclass(frozen=True, slots=True)
class ProcessingMetadata:
    """
    Metadata describing the current processing cycle.
    """

    symbol: str

    timeframe: str

    sequence: int

    timestamp: datetime

    attributes: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Market Structure Context
# ============================================================================


@dataclass(frozen=True, slots=True)
class MarketStructureContext:
    """
    Immutable context supplied to every Market Structure detector.

    The context contains only published information.

    Detector runtime state is intentionally excluded.
    """

    # Current completed market bar
    current_bar: MarketBar

    # Previously published events
    events: tuple[MarketEvent, ...] = ()

    # Active price zones
    active_zones: tuple[PriceZone, ...] = ()

    # Published measurements
    measurements: tuple[Measurement, ...] = ()

    # Processing metadata
    metadata: ProcessingMetadata | None = None