"""
Core data models for the Signal Generation module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class SignalDirection(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


# Backward compatibility
SignalType = SignalDirection


class SignalStrength(Enum):
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"
    VERY_STRONG = "VERY_STRONG"


@dataclass
class TradingSignal:
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Old API
    direction: SignalDirection = SignalDirection.HOLD

    # New API
    signal: SignalDirection | None = None

    strength: SignalStrength = SignalStrength.WEAK

    confidence: float = 0.0

    # Old API
    reasons: list[str] = field(default_factory=list)

    # New API
    reason: str = ""

    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.signal is None:
            self.signal = self.direction
        else:
            self.direction = self.signal

        if not self.reason and self.reasons:
            self.reason = "; ".join(self.reasons)

        if not self.reasons and self.reason:
            self.reasons = [self.reason]