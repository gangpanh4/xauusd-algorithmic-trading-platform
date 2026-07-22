"""
Probability evidence conditioner.

Applies market regime context to evidence scores
before probability aggregation.
"""

from __future__ import annotations

from core.regime_detector.models import MarketRegime

from .models import EvidenceScore


class RegimeConditioner:
    """
    Adjust evidence scores using the current
    market regime.

    Version 1 performs no weighting changes.
    Future versions will implement
    regime-dependent evidence weighting based on
    research and validation.
    """

    def condition(
        self,
        evidence: list[EvidenceScore],
        regime: MarketRegime | None,
    ) -> list[EvidenceScore]:
        """
        Apply regime conditioning.

        Version 1 simply returns the evidence
        unchanged.
        """

        _ = regime
        return evidence