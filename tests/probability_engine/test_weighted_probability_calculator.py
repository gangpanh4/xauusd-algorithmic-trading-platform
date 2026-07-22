from __future__ import annotations

import pytest

from core.feature_engineering.models import (
    Feature,
    FeatureVector,
)
from core.probability_engine.feature_weight import (
    FeatureWeight,
)
from core.probability_engine.weight_repository import (
    WeightRepository,
)
from core.probability_engine.weighted_probability_calculator import (
    WeightedProbabilityCalculator,
)


def make_features() -> FeatureVector:
    """
    Create a sample FeatureVector.
    """

    features = FeatureVector()

    features.add(
        Feature(
            name="structure_confidence",
            value=0.80,
            family="structure",
        )
    )

    features.add(
        Feature(
            name="current_trend",
            value=1.0,
            family="structure",
        )
    )

    features.add(
        Feature(
            name="has_bos",
            value=1.0,
            family="structure",
        )
    )

    return features


def test_weighted_probability() -> None:
    repository = WeightRepository()

    repository.set(
        FeatureWeight(
            feature_name="structure_confidence",
            weight=0.40,
        )
    )

    repository.set(
        FeatureWeight(
            feature_name="current_trend",
            weight=0.30,
        )
    )

    repository.set(
        FeatureWeight(
            feature_name="has_bos",
            weight=0.30,
        )
    )

    calculator = WeightedProbabilityCalculator(
        repository,
    )

    probability = calculator.calculate(
        make_features(),
    )

    assert 0.0 <= probability <= 1.0


def test_disabled_feature_is_ignored() -> None:
    repository = WeightRepository()

    repository.set(
        FeatureWeight(
            feature_name="structure_confidence",
            weight=1.0,
        )
    )

    repository.set(
        FeatureWeight(
            feature_name="current_trend",
            weight=1.0,
            enabled=False,
        )
    )

    calculator = WeightedProbabilityCalculator(
        repository,
    )

    probability = calculator.calculate(
        make_features(),
    )

    assert probability == pytest.approx(0.80)


def test_unknown_features_are_ignored() -> None:
    repository = WeightRepository()

    calculator = WeightedProbabilityCalculator(
        repository,
    )

    assert calculator.calculate(
        make_features(),
    ) == pytest.approx(0.0)


def test_probability_clamped() -> None:
    features = FeatureVector()

    features.add(
        Feature(
            name="structure_confidence",
            value=100.0,
            family="structure",
        )
    )

    repository = WeightRepository()

    repository.set(
        FeatureWeight(
            feature_name="structure_confidence",
            weight=1.0,
        )
    )

    calculator = WeightedProbabilityCalculator(
        repository,
    )

    probability = calculator.calculate(
        features,
    )

    assert 0.0 <= probability <= 1.0