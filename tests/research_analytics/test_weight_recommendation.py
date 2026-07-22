from __future__ import annotations

import pytest

from core.research_analytics.weight_recommendation import (
    WeightRecommendation,
)


def test_weight_recommendation_fields() -> None:
    """
    WeightRecommendation should store all values correctly.
    """

    recommendation = WeightRecommendation(
        feature_name="bos_strength",
        current_weight=0.60,
        recommended_weight=0.82,
        confidence=0.91,
        reason="Large winner/loser separation.",
    )

    assert recommendation.feature_name == "bos_strength"
    assert recommendation.current_weight == pytest.approx(0.60)
    assert recommendation.recommended_weight == pytest.approx(0.82)
    assert recommendation.confidence == pytest.approx(0.91)
    assert (
        recommendation.reason
        == "Large winner/loser separation."
    )


def test_recommendation_can_reduce_weight() -> None:
    """
    Recommendations may reduce feature weights.
    """

    recommendation = WeightRecommendation(
        feature_name="probability",
        current_weight=1.00,
        recommended_weight=0.20,
        confidence=0.34,
        reason="Weak separation between winners and losers.",
    )

    assert recommendation.recommended_weight < recommendation.current_weight


def test_zero_weight_supported() -> None:
    """
    A feature can be recommended for complete removal.
    """

    recommendation = WeightRecommendation(
        feature_name="noise_feature",
        current_weight=0.40,
        recommended_weight=0.00,
        confidence=0.97,
        reason="No predictive value.",
    )

    assert recommendation.recommended_weight == pytest.approx(0.0)