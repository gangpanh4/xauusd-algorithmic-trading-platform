"""
Core data models for the Signal Generation module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SignalType(Enum):
    """
    High-level trading signal.
    """

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class SignalStrength(Enum):
    """
    Strength of the generated signal.
    """

    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"
    VERY_STRONG = "VERY_STRONG"


@dataclass(frozen=True)
class TradingSignal:
    """
    Final signal produced by the Signal Generator.
    """

    timestamp: datetime

    signal: SignalType

    strength: SignalStrength

    confidence: float

    reason: str

    metadata: dict[str, Any] = field(default_factory=dict)