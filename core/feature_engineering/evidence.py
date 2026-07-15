"""
Feature Engineering evidence models.

Defines the standardized evidence bundle consumed
by feature extractors.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.market_structure.models import MarketStructureResult
from core.regime_detector.models import MarketRegime


@dataclass(slots=True)
class FeatureEvidence:
    """
    Aggregated evidence supplied to the Feature
    Engineering layer.

    Each extractor consumes only the evidence it
    requires while sharing one common interface.
    """

    market_structure: MarketStructureResult | None = None

    regime: MarketRegime | None = None