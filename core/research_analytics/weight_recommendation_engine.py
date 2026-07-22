"""
Weight Recommendation Engine.

Generates weight recommendations from feature statistics.
"""

from __future__ import annotations

from core.research_analytics.feature_statistics_engine import (
    FeatureStatisticsEngine,
)
from core.research_analytics.storage import (
    ResearchStorage,
)
from core.research_analytics.weight_recommendation import (
    WeightRecommendation,
)


class WeightRecommendationEngine:
    """
    Recommend feature weights based on historical
    winner/loser separation.
    """

    def __init__(
        self,
        storage: ResearchStorage,
    ) -> None:
        self.storage = storage

    def analyze(
        self,
    ) -> list[WeightRecommendation]:
        """
        Produce recommendations for every feature.
        """

        statistics = FeatureStatisticsEngine(
            self.storage,
        ).analyze()

        recommendations: list[
            WeightRecommendation
        ] = []

        for stat in statistics:

            gap = abs(stat.gap)

            confidence = min(
                1.0,
                gap,
            )

            recommendations.append(
                WeightRecommendation(
                    feature_name=stat.feature_name,
                    current_weight=1.0,
                    recommended_weight=confidence,
                    confidence=confidence,
                    reason=(
                        "Higher separation between winners "
                        "and losers increases the suggested weight."
                    ),
                )
            )

        recommendations.sort(
            key=lambda recommendation: recommendation.confidence,
            reverse=True,
        )

        return recommendations

    def generate_weight_map(
        self,
    ) -> dict[str, float]:
        """
        Generate normalized feature weights that can be consumed
        by the probability engine.

        The returned weights always sum to 1.0.
        """

        recommendations = self.analyze()

        if not recommendations:
            return {}

        total_weight = sum(
            recommendation.recommended_weight
            for recommendation in recommendations
        )

        if total_weight <= 0.0:
            return {}

        normalized_weights: dict[str, float] = {}
        for recommendation in recommendations:

            normalized_weights[
                recommendation.feature_name
            ] = (
                recommendation.recommended_weight
                / total_weight
            )

        return normalized_weights