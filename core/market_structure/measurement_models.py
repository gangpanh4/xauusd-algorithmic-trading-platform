"""
Market Structure Measurements

This module defines immutable measurement models produced by
Market Structure detectors.

Measurements represent raw quantitative observations and are
consumed by Feature Engineering.

Author: Trading Intelligence Platform
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ============================================================================
# Measurement Types
# ============================================================================


class MeasurementType(str, Enum):
    """Supported Market Structure measurement types."""

    SWING_STRENGTH = "swing_strength"
    SWING_QUALITY = "swing_quality"

    BOS_STRENGTH = "bos_strength"
    BOS_DISTANCE = "bos_distance"

    CHOCH_STRENGTH = "choch_strength"

    LIQUIDITY_QUALITY = "liquidity_quality"
    LIQUIDITY_DISTANCE = "liquidity_distance"

    ORDER_BLOCK_QUALITY = "order_block_quality"

    FAIR_VALUE_GAP_SIZE = "fair_value_gap_size"

    BREAKER_BLOCK_QUALITY = "breaker_block_quality"

    MITIGATION_STRENGTH = "mitigation_strength"


# ============================================================================
# Measurement Metadata
# ============================================================================


@dataclass(frozen=True, slots=True)
class MeasurementMetadata:
    """
    Additional information describing a Measurement.
    """

    detector: str
    symbol: str | None = None
    timeframe: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Measurement
# ============================================================================


@dataclass(frozen=True, slots=True)
class Measurement:
    """
    Immutable quantitative observation produced by a detector.
    """

    type: MeasurementType

    value: float

    timestamp: datetime

    metadata: MeasurementMetadata