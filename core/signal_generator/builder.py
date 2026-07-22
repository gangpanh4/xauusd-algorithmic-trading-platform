"""
Signal Generator Builder.

Constructs TradingSignal instances from evaluated signal data.
"""

from __future__ import annotations

from .models import (
    SignalDirection,
    SignalScore,
    SignalStrength,
    TradingSignal,
)


class SignalBuilder:
    """
    Builds TradingSignal objects.

    This class is responsible only for constructing
    TradingSignal instances from already evaluated inputs.
    """

    def build(
        self,
        *,
        direction: SignalDirection,
        score: SignalScore,
        strength: SignalStrength,
        confidence: float,
        reason: str,
    ) -> TradingSignal:

        return TradingSignal(
            signal=direction,
            strength=strength,
            confidence=confidence,
            decision_score=score.normalized,
            reason=reason,
        )