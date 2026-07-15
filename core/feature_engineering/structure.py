"""
Structure feature extractor.

Extracts standardized market structure features from
the EvidenceContext.
"""

from __future__ import annotations

from core.market_structure.enums import TrendDirection

from .evidence import FeatureEvidence
from .encoders import encode_trend
from .extractor import FeatureExtractor
from .models import Feature, FeatureVector


class StructureFeatureExtractor(FeatureExtractor):
    """
    Extract market structure features.

    Version 1 establishes the extractor contract.
    Future versions will use outputs from the
    Market Structure Engine.
    """

    def extract(
        self,
        evidence: FeatureEvidence,
        feature_vector: FeatureVector,
    ) -> None:
        """
        Extract standardized market structure features.
        """

        market_structure = evidence.market_structure

        if market_structure is None:
            return

        feature_vector.add(
            Feature(
                name="structure_confidence",
                value=market_structure.structure_confidence,
                confidence=1.0,
                normalized=True,
                family="structure",
                source="market_structure",
            )
        )

        # Current market trend
        if market_structure.current_trend is not None:

            feature_vector.add(
                Feature(
                    name="current_trend",
                    value=encode_trend(
                        market_structure.current_trend,
                    ),
                    confidence=market_structure.structure_confidence,
                    normalized=False,
                    family="structure",
                    source="market_structure",
                )
            )

        # Break of Structure presence
        feature_vector.add(
            Feature(
                name="has_bos",
                value=1.0 if market_structure.last_bos is not None else 0.0,
                confidence=market_structure.structure_confidence,
                normalized=False,
                family="structure",
                source="market_structure",
            )
        )

        # Break of Structure strength
        if market_structure.last_bos is not None:

            feature_vector.add(
                Feature(
                    name="bos_break_distance",
                    value=market_structure.last_bos.break_distance,
                    confidence=market_structure.structure_confidence,
                    normalized=False,
                    family="structure",
                    source="market_structure",
                )
            )

        # Change of Character presence
        feature_vector.add(
            Feature(
                name="has_choch",
                value=1.0 if market_structure.last_choch is not None else 0.0,
                confidence=market_structure.structure_confidence,
                normalized=False,
                family="structure",
                source="market_structure",
            )
        )

        # Change of Character strength
        if market_structure.last_choch is not None:

            feature_vector.add(
                Feature(
                    name="choch_break_distance",
                    value=market_structure.last_choch.break_distance,
                    confidence=market_structure.structure_confidence,
                    normalized=False,
                    family="structure",
                    source="market_structure",
                )
            )