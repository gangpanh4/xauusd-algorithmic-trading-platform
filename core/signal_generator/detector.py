"""
Signal Generation Engine.
"""

from __future__ import annotations

from datetime import UTC, datetime

from core.regime_detector.models import (
    MarketRegime,
    RegimeLabel,
)

from .config import SignalGeneratorConfig
from .models import (
    SignalStrength,
    SignalType,
    TradingSignal,
)
from .state import SignalGeneratorState
from core.trade_quality.manager import TradeQualityManager


class SignalGenerator:
    """
    Converts MarketRegime into a TradingSignal.

    This implementation is intentionally based on the current
    MarketRegimeDetector architecture.

    Intelligence v2 will replace this later.
    """

    def __init__(
        self,
        config: SignalGeneratorConfig,
        opportunity_ranker=None,
    ) -> None:

        self.config = config
        self.state = SignalGeneratorState()

        # kept for future integration
        self.opportunity_ranker = opportunity_ranker
        self.trade_quality = TradeQualityManager()

    def generate_signal(
        self,
        regime: MarketRegime,
    ) -> TradingSignal:
        """
        Generate a signal from the detected market regime.
        """

        confidence = regime.confidence

        self.state.trend_scores[regime.trend_score] += 1

        self.state.momentum_scores[regime.momentum_score] += 1

        self.state.volatility_scores[regime.volatility_score] += 1

        self.state.ema_scores[regime.ema_score] += 1

        self.state.choppiness_scores[regime.choppiness_score] += 1

        self.state.total_scores[regime.total_score] += 1

        current_regime = regime.primary_regime
        previous_regime = self.state.last_regime

        # -------------------------------------------------
        # Transition-based signal generation
        # -------------------------------------------------

        signal = SignalType.HOLD

        if (
            current_regime == RegimeLabel.TRENDING_BULL
            and previous_regime != RegimeLabel.TRENDING_BULL
            and confidence >= self.config.minimum_signal_confidence
            and regime.total_score >= self.config.minimum_total_score
        ):
            signal = SignalType.BUY

        elif (
            current_regime == RegimeLabel.TRENDING_BEAR
            and previous_regime != RegimeLabel.TRENDING_BEAR
            and confidence >= self.config.minimum_signal_confidence
            and regime.total_score >= self.config.minimum_total_score
        ):
            signal = SignalType.SELL

        # -------------------------------------------------
        # Signal Strength
        # -------------------------------------------------
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
            reason=(
                f"Regime={regime.primary_regime.value}, "
                f"confidence={confidence:.3f}"
            ),
        )

        self.state.last_regime = current_regime

        self._update_state(result)

        return result

    def _update_state(
        self,
        signal: TradingSignal,
    ) -> None:

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