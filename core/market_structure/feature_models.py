"""
Market Structure Feature Models

This module defines immutable feature models produced by Feature Engineering.

Features are engineered from raw Measurements and consumed by downstream
systems such as:

- Probability Engine
- Research Analytics
- Machine Learning
- Backtesting

Author: Trading Intelligence Platform
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ============================================================================
# Feature Types
# ============================================================================


class FeatureType(str, Enum):
    """Supported Market Structure feature types."""

    STRUCTURE = "structure"
    MOMENTUM = "momentum"
    TREND = "trend"
    LIQUIDITY = "liquidity"
    VOLATILITY = "volatility"
    PRICE_ACTION = "price_action"
    CONFLUENCE = "confluence"
    CUSTOM = "custom"


# ============================================================================
# Feature Metadata
# ============================================================================


@dataclass(frozen=True, slots=True)
class FeatureMetadata:
    """
    Additional information describing a Feature.
    """

    source_measurements: tuple[str, ...] = ()

    strategy: str | None = None

    timeframe: str | None = None

    symbol: str | None = None

    attributes: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Feature
# ============================================================================


@dataclass(frozen=True, slots=True)
class Feature:
    """
    Immutable engineered feature.

    A Feature is derived from one or more Measurements and represents
    normalized or transformed information suitable for downstream
    analytical systems.
    """

    name: str

    feature_type: FeatureType

    value: float

    normalized_value: float

    confidence: float

    timestamp: datetime

    metadata: FeatureMetadata