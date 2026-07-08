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

class BOSEventType(Enum):
    """
    Type of BOSEvent.
    """

    DETECTED = auto()
    CLEARED = auto()


class BOSDetectorStateType(Enum):
    """
    Type of BOSDetectorState.
    """

    ACTIVE = auto()
    INACTIVE = auto()


class BOSDetectorConfigKey(Enum):
    """
    Key for BOSDetectorConfig.
    """

    PARAM1 = auto()
    PARAM2 = auto()
