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

    # Version 2
    decision_score: float = 0.0

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


@dataclass(slots=True, frozen=True)
class SignalScore:
    """
    Overall signal strength.

    Normalized to the range [0.0, 1.0].
    """

    value: float

    @property
    def normalized(self) -> float:
        return max(0.0, min(1.0, self.value))