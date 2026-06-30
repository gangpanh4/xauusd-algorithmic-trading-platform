"""
Trading rule evaluation for the Signal Generation module.
"""

from __future__ import annotations

from core.regime_detector.models import (
    MarketRegime,
    RegimeLabel,
)

from .models import (
    SignalType,
)


def evaluate_signal(
    regime: MarketRegime,
) -> SignalType:
    """
    Evaluate the market regime and return a basic trading signal.
    """

    if regime.primary_regime == RegimeLabel.TRENDING_BULL:
        return SignalType.BUY

    if regime.primary_regime == RegimeLabel.TRENDING_BEAR:
        return SignalType.SELL

    return SignalType.HOLD