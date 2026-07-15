"""
Feature Engineering Engine.

Transforms an EvidenceContext into a standardized
FeatureVector for downstream intelligence modules.
"""

from __future__ import annotations

from .config import FeatureEngineeringConfig
from .evidence import FeatureEvidence
from .extractor import FeatureExtractor
from .liquidity import LiquidityFeatureExtractor
from .models import Feature, FeatureVector
from .regime import RegimeFeatureExtractor
from .registry import FeatureRegistry
from .state import FeatureEngineeringState
from .structure import StructureFeatureExtractor


class FeatureEngineeringEngine:
    """
    Converts EvidenceContext into a FeatureVector.

    Version 1 intentionally implements only the
    infrastructure. Individual feature extraction
    will be added incrementally in future versions.
    """

    def __init__(
        self,
        config: FeatureEngineeringConfig | None = None,
    ) -> None:
        self.config = config or FeatureEngineeringConfig()
        self.state = FeatureEngineeringState()

        self.registry = FeatureRegistry()

        self.extractors: list[FeatureExtractor] = [
            StructureFeatureExtractor(),
            LiquidityFeatureExtractor(),
        ]

        self.regime_extractor = RegimeFeatureExtractor()

    def reset(self) -> None:
        """
        Reset engine state.
        """
        self.state.reset()

    @property
    def registered_feature_count(self) -> int:
        """
        Number of registered features.
        """
        return self.registry.size

    @property
    def feature_count(self) -> int:
        """
        Number of features produced during the latest run.
        """
        return self.state.latest_features.size

    def process(
        self,
        evidence: FeatureEvidence,
    ) -> FeatureVector:
        """
        Build a standardized FeatureVector.

        Version 1 returns an empty feature vector.
        Future versions will populate this vector
        using Market Structure, Price Action,
        Liquidity, Regime and Volatility evidence.
        """

        vector = FeatureVector()

        for extractor in self.extractors:
            extractor.extract(
                evidence,
                vector,
            )

        self.state.latest_features = vector
        self.state.processed_count += 1

        return vector

    def create_evidence(
        self,
        *,
        market_structure=None,
        regime=None,
    ) -> FeatureEvidence:
        """
        Create a FeatureEvidence object.

        This helper keeps FeatureEngineeringEngine
        independent from the Trading Pipeline while
        providing a standard way to build evidence.
        """

        return FeatureEvidence(
            market_structure=market_structure,
            regime=regime,
        )

    def _add_feature(
        self,
        vector: FeatureVector,
        *,
        name: str,
        value: float,
        family: str,
        source: str,
        confidence: float = 1.0,
        normalized: bool = True,
    ) -> None:
        """
        Add a standardized feature to the feature vector.
        """

        if confidence < self.config.minimum_confidence:
            return

        vector.add(
            Feature(
                name=name,
                value=value,
                confidence=confidence,
                normalized=normalized,
                family=family,
                source=source,
            )
        )