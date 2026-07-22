"""
Feature Engineering evidence models.

Defines the standardized evidence bundle consumed
by feature extractors.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.market_context import (
    MarketContext,
)

from core.market_structure.models import (
    MarketStructureResult,
)

from core.regime_detector.models import (
    MarketRegime,
)


@dataclass(slots=True)
class FeatureEvidence:
    """
    Aggregated evidence supplied to the Feature
    Engineering layer.

    FeatureEvidence is derived from MarketContext,
    but remains independent so Feature Engineering
    only receives the information it actually needs.
    """

    market_structure: MarketStructureResult | None = None

    regime: MarketRegime | None = None

    @classmethod
    def from_market_context(
        cls,
        context: MarketContext,
    ) -> "FeatureEvidence":
        """
        Build FeatureEvidence from a MarketContext.
        """

        return cls(
            market_structure=context.market_structure,
            regime=context.market_regime,
        )