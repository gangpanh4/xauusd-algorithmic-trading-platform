"""
Signal Generation Engine.
"""

from __future__ import annotations

from .config import SignalGeneratorConfig
from .models import (
    SignalStrength,
    SignalType,
    TradingSignal,
)
from .rules import evaluate_signal
from .state import SignalGeneratorState

from core.regime_detector.models import (
    MarketRegime,
)

from datetime import datetime, UTC


class SignalGenerator:
    """
    Converts Market Regimes into Trading Signals.
    """

    def __init__(
        self,
        config: SignalGeneratorConfig,
    ) -> None:

        self.config = config

        self.state = SignalGeneratorState()

    def generate_signal(
        self,
        regime: MarketRegime,
    ) -> TradingSignal:
        """
        Generate a trading signal from the current market regime.
        """

        signal = evaluate_signal(regime)

        confidence = regime.confidence

        if confidence >= 0.90:
            strength = SignalStrength.VERY_STRONG

        elif confidence >= 0.75:
            strength = SignalStrength.STRONG

        elif confidence >= 0.60:
            strength = SignalStrength.MODERATE

        else:
            strength = SignalStrength.WEAK

        result = TradingSignal(
            timestamp=datetime.now(UTC),
            signal=signal,
            strength=strength,
            confidence=confidence,
            reason=f"Market regime: {regime.primary_regime.value}",
        )

        self._update_state(result)

        return result

    def _update_state(
        self,
        signal: TradingSignal,
    ) -> None:
        """
        Update internal generator state.
        """

        self.state.last_signal = signal.signal

        self.state.last_signal_time = signal.timestamp

        self.state.last_result = signal

        self.state.initialized = True

        self.state.processed_bar_count += 1

        if signal.signal == SignalType.HOLD:
            self.state.consecutive_hold_count += 1
        else:
            self.state.consecutive_hold_count = 0

        self.state.bars_since_last_signal = 0