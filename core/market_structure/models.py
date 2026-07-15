"""
Shared data models for the Market Structure Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.market_structure.enums import (
    BreakType,
    SwingType,
    TrendDirection,
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
    """

    timestamp: datetime

    # Event classification.
    break_type: BreakType

    # Structural direction.
    direction: TrendDirection

    # Swing that was broken.
    swing_point: SwingPoint

    # Price that confirmed the break.
    break_price: float

    # Candle where the BOS became confirmed.
    confirmation_index: int

    # Version 2 evidence

    # Absolute distance beyond the broken swing.
    break_distance: float = 0.0


@dataclass(slots=True, frozen=True)
class CHOCHEvent:
    """
    Immutable representation of a confirmed Change of Character.
    """

    timestamp: datetime

    # Event classification.
    break_type: BreakType

    # Structural direction.
    direction: TrendDirection

    # Swing that was broken.
    swing_point: SwingPoint

    # Price that confirmed the break.
    break_price: float

    # Candle where the CHOCH became confirmed.
    confirmation_index: int

    # Version 2 evidence

    # Absolute distance beyond the protected swing.
    break_distance: float = 0.0


@dataclass(slots=True, frozen=True)
class LiquidityLevel:
    """
    Represents a price level where liquidity is expected.

    Examples:
    - Previous swing high (buy-side liquidity)
    - Previous swing low (sell-side liquidity)
    """

    timestamp: datetime
    price: float
    swing_point: SwingPoint
    is_buy_side: bool


@dataclass(slots=True, frozen=True)
class LiquiditySweepEvent:
    """
    Represents a confirmed liquidity sweep.

    A sweep occurs when price takes a liquidity level
    and confirms the grab.
    """

    timestamp: datetime
    liquidity_level: LiquidityLevel
    sweep_price: float
    confirmation_index: int

    # Version 2 evidence

    # Absolute distance beyond the swept liquidity level.
    sweep_distance: float = 0.0


@dataclass(slots=True, frozen=True)
class MarketStructureResult:
    """
    Aggregated output produced by the MarketStructureEngine.

    This is the single object consumed by downstream
    engines (Price Action, Confluence, etc.).
    """

    timestamp: datetime

    last_swing: SwingPoint | None

    last_bos: BOSEvent | None

    last_choch: CHOCHEvent | None

    last_liquidity: LiquiditySweepEvent | None

    current_trend: TrendDirection | None

    structure_confidence: float