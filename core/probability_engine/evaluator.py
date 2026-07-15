"""
Base probability evaluator.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.feature_engineering.models import FeatureVector

from .models import EvidenceScore


class ProbabilityEvaluator(ABC):
    """
    Base interface for all probability evaluators.
    """

    @abstractmethod
    def evaluate(
        self,
        features: FeatureVector,
    ) -> EvidenceScore:
        """
        Evaluate one evidence family.
        """
        raise NotImplementedError