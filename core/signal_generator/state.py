"""
State management for the Signal Generation module.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, UTC

from core.regime_detector.models import RegimeLabel

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

    last_regime: RegimeLabel | None = None

    # -------------------------------------------------
    # Experiment 002A
    # Regime Intelligence Statistics
    # -------------------------------------------------

    trend_scores: Counter = field(default_factory=Counter)

    momentum_scores: Counter = field(default_factory=Counter)

    volatility_scores: Counter = field(default_factory=Counter)

    ema_scores: Counter = field(default_factory=Counter)

    choppiness_scores: Counter = field(default_factory=Counter)

    total_scores: Counter = field(default_factory=Counter)

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

        self.last_regime = None