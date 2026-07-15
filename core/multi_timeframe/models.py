"""
Multi-Timeframe data models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .enums import (
    MarketBias,
    Timeframe,
    TimeframeAlignment,
)


@dataclass(slots=True)
class TimeframeState:
    """
    Analysis state for a single timeframe.

    This is the common contract shared by all
    timeframe analyses (W1, D1, H4, H1, M15, M5).
    """

    timeframe: Timeframe

    timestamp: datetime | None = None

    bias: MarketBias = MarketBias.NEUTRAL

    alignment: TimeframeAlignment = (
        TimeframeAlignment.PARTIAL
    )

    confidence: float = 0.0

    market_structure: Any | None = None

    price_action: Any | None = None

    confluence: Any | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(slots=True)
class MultiTimeframeResult:
    """
    Combined analysis across all supported
    timeframes.
    """

    weekly: TimeframeState

    daily: TimeframeState

    h4: TimeframeState

    h1: TimeframeState

    m15: TimeframeState

    m5: TimeframeState

    overall_bias: MarketBias = (
        MarketBias.NEUTRAL
    )

    overall_alignment: TimeframeAlignment = (
        TimeframeAlignment.PARTIAL
    )

    confidence: float = 0.0

    timestamp: datetime | None = None