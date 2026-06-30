"""
State management for the Signal Generation module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import (
    TradingSignal,
    SignalType,
)


@dataclass
class SignalGeneratorState:
    """
    Maintains the internal state of the Signal Generator.
    """

    last_signal: SignalType = SignalType.HOLD

    last_signal_time: datetime | None = None

    last_result: TradingSignal | None = None

    initialized: bool = False

    bars_since_last_signal: int = 0

    consecutive_hold_count: int = 0

    processed_bar_count: int = 0

    def reset(self) -> None:
        """
        Reset the signal generator to its initial state.
        """

        self.last_signal = SignalType.HOLD

        self.last_signal_time = None

        self.last_result = None

        self.initialized = False

        self.bars_since_last_signal = 0

        self.consecutive_hold_count = 0

        self.processed_bar_count = 0