"""
Liquidity feature extractor.

Extracts standardized liquidity features from
the EvidenceContext.
"""

from __future__ import annotations

from .evidence import FeatureEvidence
from .extractor import FeatureExtractor
from .models import Feature, FeatureVector


class LiquidityFeatureExtractor(FeatureExtractor):
    """
    Extract liquidity-related engineered features.

    Version 1 consumes the liquidity evidence already
    produced by the Market Structure Engine.
    """

    def extract(
        self,
        evidence: FeatureEvidence,
        feature_vector: FeatureVector,
    ) -> None:
        """
        Extract standardized liquidity features.
        """

        market_structure = evidence.market_structure

        if market_structure is None:
            return

        feature_vector.add(
            Feature(
                name="has_liquidity",
                value=(
                    1.0
                    if market_structure.last_liquidity is not None
                    else 0.0
                ),
                confidence=market_structure.structure_confidence,
                normalized=False,
                family="liquidity",
                source="market_structure",
            )
        )

        # Liquidity sweep strength
        if market_structure.last_liquidity is not None:

            feature_vector.add(
                Feature(
                    name="liquidity_sweep_distance",
                    value=market_structure.last_liquidity.sweep_distance,
                    confidence=market_structure.structure_confidence,
                    normalized=False,
                    family="liquidity",
                    source="market_structure",
                )
            )