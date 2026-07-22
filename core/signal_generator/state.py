"""
State management for the Signal Generation module.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from core.regime_detector.models import RegimeLabel

from .models import SignalType, TradingSignal


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

    last_emitted_signal: SignalType = SignalType.HOLD

    last_emitted_signal_time: datetime | None = None

    last_emitted_regime: RegimeLabel | None = None

    # -------------------------------------------------
    # Experiment 002A
    # Regime Intelligence Statistics
    # -------------------------------------------------

    trend_scores: Counter[float] = field(default_factory=Counter)

    momentum_scores: Counter[float] = field(default_factory=Counter)

    volatility_scores: Counter[float] = field(default_factory=Counter)

    ema_scores: Counter[float] = field(default_factory=Counter)

    choppiness_scores: Counter[float] = field(default_factory=Counter)

    total_scores: Counter[float] = field(default_factory=Counter)

    def record_result(
        self,
        result: TradingSignal,
        *,
        regime: RegimeLabel,
    ) -> None:
        """
        Record one processed signal-generation result.

        HOLD results advance the number of bars since the last emitted
        BUY or SELL signal. Emitted signals reset that counter and update
        the dedicated emitted-signal fields used by cooldown and duplicate
        policies.
        """

        signal = result.signal or result.direction

        self.last_signal = signal
        self.last_signal_time = result.timestamp
        self.last_result = result
        self.last_regime = regime
        self.initialized = True
        self.processed_bar_count += 1

        if signal is SignalType.HOLD:
            self.consecutive_hold_count += 1
            self.bars_since_last_signal += 1
            return

        self.consecutive_hold_count = 0
        self.bars_since_last_signal = 0
        self.last_emitted_signal = signal
        self.last_emitted_signal_time = result.timestamp
        self.last_emitted_regime = regime

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
        self.last_emitted_signal = SignalType.HOLD
        self.last_emitted_signal_time = None
        self.last_emitted_regime = None

        self.trend_scores.clear()
        self.momentum_scores.clear()
        self.volatility_scores.clear()
        self.ema_scores.clear()
        self.choppiness_scores.clear()
        self.total_scores.clear()
