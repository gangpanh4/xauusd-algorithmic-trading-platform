"""
Base feature extractor interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .evidence import FeatureEvidence
from .models import FeatureVector


class FeatureExtractor(ABC):
    """
    Base class for all feature extractors.
    """

    @abstractmethod
    def extract(
        self,
        evidence: FeatureEvidence,
        feature_vector: FeatureVector,
    ) -> None:
        """
        Extract engineered features into the feature vector.
        """
        raise NotImplementedError