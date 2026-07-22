"""
Market Structure Result

This module defines the immutable result returned by the
Market Structure Engine after processing a completed MarketBar.

Author: Trading Intelligence Platform
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .events import MarketEvent
from .feature_models import Feature
from .measurement_models import Measurement
from .zones import PriceZone


# ============================================================================
# Result Metadata
# ============================================================================


@dataclass(frozen=True, slots=True)
class ResultMetadata:
    """
    Metadata describing the processing result.
    """

    processing_time_ms: float = 0.0

    detector_count: int = 0

    successful: bool = True

    timestamp: datetime = field(default_factory=datetime.utcnow)

    attributes: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Market Structure Result
# ============================================================================


@dataclass(frozen=True, slots=True)
class MarketStructureResult:
    """
    Immutable snapshot of the Market Structure Engine.

    This object represents the complete published state after
    processing a single completed MarketBar.
    """

    events: tuple[MarketEvent, ...] = ()

    active_zones: tuple[PriceZone, ...] = ()

    measurements: tuple[Measurement, ...] = ()

    features: tuple[Feature, ...] = ()

    metadata: ResultMetadata = field(default_factory=ResultMetadata)