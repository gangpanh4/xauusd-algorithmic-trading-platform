"""
Weighted Probability Calculator.
"""

from __future__ import annotations

from core.feature_engineering.models import (
    FeatureVector,
)

from core.probability_engine.weight_repository import (
    WeightRepository,
)

from core.probability_engine.feature_normalizer import (
    FeatureNormalizer,
)


class WeightedProbabilityCalculator:
    """
    Compute probability from normalized engineered features.

    Active repository weights define the complete evidence model. Missing
    features contribute zero instead of being removed from the denominator,
    which prevents sparse feature vectors from receiving inflated scores.
    Each configured feature is evaluated at most once.
    """

    def __init__(
        self,
        repository: WeightRepository,
    ) -> None:

        self.repository = repository
        self.normalizer = FeatureNormalizer()

    def calculate(
        self,
        features: FeatureVector,
    ) -> float:
        """
        Calculate weighted probability using normalized features.
        """

        active_weights = tuple(
            weight
            for weight in self.repository.all()
            if weight.is_active
        )

        total_weight = sum(
            weight.weight
            for weight in active_weights
        )

        if total_weight <= 0.0:
            return 0.0

        feature_by_name = {
            feature.name: feature
            for feature in features.features
        }

        weighted_sum = 0.0

        for weight in active_weights:
            feature = feature_by_name.get(
                weight.feature_name,
            )

            if feature is None:
                continue

            value = self.normalizer.normalize(
                feature,
            )

            weighted_sum += (
                value
                * weight.weight
            )

        probability = (
            weighted_sum
            / total_weight
        )

        if probability < 0.0:
            return 0.0

        if probability > 1.0:
            return 1.0

        return probability
