"""
Market Structure Price Zones

This module defines immutable price zones used throughout the
Market Structure Engine.

Zones represent persistent areas of interest in price rather than
instantaneous market events.

Author: Trading Intelligence Platform
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


# ============================================================================
# Zone Type
# ============================================================================


class ZoneType(str, Enum):
    """Supported price zone types."""

    LIQUIDITY = "liquidity"

    ORDER_BLOCK = "order_block"

    FAIR_VALUE_GAP = "fair_value_gap"

    BREAKER_BLOCK = "breaker_block"


# ============================================================================
# Zone Direction
# ============================================================================


class ZoneDirection(str, Enum):
    """Directional bias of a price zone."""

    BULLISH = "bullish"

    BEARISH = "bearish"

    NEUTRAL = "neutral"


# ============================================================================
# Zone Lifecycle
# ============================================================================


class ZoneLifecycle(str, Enum):
    """Lifecycle state of a price zone."""

    CREATED = "created"

    CONFIRMED = "confirmed"

    ACTIVE = "active"

    TESTED = "tested"

    MITIGATED = "mitigated"

    INVALIDATED = "invalidated"

    EXPIRED = "expired"


# ============================================================================
# Zone Metadata
# ============================================================================


@dataclass(frozen=True, slots=True)
class ZoneMetadata:
    """
    Additional information describing a price zone.
    """

    detector: str

    symbol: str | None = None

    timeframe: str | None = None

    attributes: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Price Zone
# ============================================================================


@dataclass(frozen=True, slots=True)
class PriceZone:
    """
    Immutable market structure price zone.
    """

    id: str = field(default_factory=lambda: str(uuid4()))

    zone_type: ZoneType = ZoneType.ORDER_BLOCK

    direction: ZoneDirection = ZoneDirection.NEUTRAL

    high: float = 0.0

    low: float = 0.0

    created_at: datetime = field(default_factory=datetime.utcnow)

    lifecycle: ZoneLifecycle = ZoneLifecycle.CREATED

    confidence: float = 1.0

    metadata: ZoneMetadata = field(
        default_factory=lambda: ZoneMetadata(detector="unknown")
    )

    @property
    def midpoint(self) -> float:
        """Return the midpoint price."""

        return (self.high + self.low) / 2.0

    @property
    def height(self) -> float:
        """Return the zone height."""

        return abs(self.high - self.low)