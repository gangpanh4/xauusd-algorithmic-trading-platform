"""
Market Structure Events

This module defines immutable market events produced by Market Structure
detectors.

Events represent confirmed structural facts that occurred in the market.

Author: Trading Intelligence Platform
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


# ============================================================================
# Event Type
# ============================================================================


class EventType(str, Enum):
    """Supported market structure event types."""

    SWING = "swing"

    BOS = "bos"

    CHOCH = "choch"

    LIQUIDITY = "liquidity"

    ORDER_BLOCK = "order_block"

    FAIR_VALUE_GAP = "fair_value_gap"

    BREAKER_BLOCK = "breaker_block"

    MITIGATION = "mitigation"


# ============================================================================
# Event Direction
# ============================================================================


class EventDirection(str, Enum):
    """Directional classification."""

    BULLISH = "bullish"
    
    BEARISH = "bearish"
    
    NEUTRAL = "neutral"


# ============================================================================
# Event Metadata
# ============================================================================


@dataclass(frozen=True, slots=True)
class EventMetadata:
    """
    Additional information describing a MarketEvent.
    """

    detector: str

    symbol: str | None = None

    timeframe: str | None = None

    attributes: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Market Event
# ============================================================================


@dataclass(frozen=True, slots=True)
class MarketEvent:
    """
    Immutable market structure event.

    Represents a confirmed structural event published by a detector.
    """

    id: str = field(default_factory=lambda: str(uuid4()))

    event_type: EventType = EventType.SWING

    direction: EventDirection = EventDirection.NEUTRAL

    price: float = 0.0

    timestamp: datetime = field(default_factory=datetime.utcnow)

    confidence: float = 1.0

    metadata: EventMetadata = field(
        default_factory=lambda: EventMetadata(detector="unknown")
    )