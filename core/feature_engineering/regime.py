"""
Regime feature extractor.

Extracts standardized market regime features.
"""

from __future__ import annotations

from .evidence import FeatureEvidence
from .extractor import FeatureExtractor
from .models import Feature, FeatureVector


class RegimeFeatureExtractor(FeatureExtractor):
    """
    Extract standardized regime features.

    Version 1 translates existing regime evidence
    into machine-learning-ready features.
    """

    def extract(
        self,
        evidence: FeatureEvidence,
        feature_vector: FeatureVector,
    ) -> None:
        """
        Extract regime features.
        """

        regime = evidence.regime

        if regime is None:
            return

        feature_vector.add(
            Feature(
                name="regime_confidence",
                value=regime.confidence,
                confidence=1.0,
                normalized=True,
                family="regime",
                source="regime_detector",
            )
        )