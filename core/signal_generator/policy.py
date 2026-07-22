"""
Signal Generator Policy.

Interprets signal scores and applies generation policies.
"""

from __future__ import annotations

from .models import SignalScore, SignalStrength


class SignalPolicy:
    """
    Applies business rules to scored trading signals.
    """

    def classify_strength(
        self,
        score: SignalScore,
    ) -> SignalStrength:
        """
        Classify the signal based on its normalized score.
        """

        value = score.normalized

        if value >= 0.80:
            return SignalStrength.VERY_STRONG

        if value >= 0.65:
            return SignalStrength.STRONG

        if value >= 0.50:
            return SignalStrength.MODERATE

        return SignalStrength.WEAK

    def should_emit(
        self,
        score: SignalScore,
    ) -> bool:
        """
        Determine whether a scored signal is strong enough
        to be emitted.
        """

        return score.normalized >= 0.50

    def is_high_quality(
        self,
        score: SignalScore,
    ) -> bool:
        """
        Return True when the signal represents
        a high-quality trading opportunity.
        """

        return score.normalized >= 0.80