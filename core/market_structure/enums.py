"""
Shared enumerations for the Market Structure Engine.

These enums define the common vocabulary used by Swing Detection,
Break of Structure (BOS), Change of Character (CHoCH), Liquidity,
Order Blocks, and Fair Value Gaps.

The goal is to provide strongly typed values rather than string literals,
ensuring consistency across all market structure modules.
"""

from __future__ import annotations

from enum import Enum, auto


class SwingType(Enum):
    """
    Type of confirmed swing.
    """

    HIGH = auto()
    LOW = auto()


class BreakType(Enum):
    """
    Type of market structure break.
    """

    BOS = auto()
    CHOCH = auto()


class TrendDirection(Enum):
    """
    Structural trend direction.
    """

    BULLISH = auto()
    BEARISH = auto()
    NEUTRAL = auto()


class LiquidityType(Enum):
    """
    Type of detected liquidity.
    """

    BUY_SIDE = auto()
    SELL_SIDE = auto()


class OrderBlockType(Enum):
    """
    Direction of an order block.
    """

    BULLISH = auto()
    BEARISH = auto()


class FairValueGapType(Enum):
    """
    Direction of a Fair Value Gap.
    """

    BULLISH = auto()
    BEARISH = auto()