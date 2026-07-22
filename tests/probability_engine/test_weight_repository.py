from __future__ import annotations

from core.probability_engine.feature_weight import (
    FeatureWeight,
)
from core.probability_engine.weight_repository import (
    WeightRepository,
)


def test_set_and_get_weight() -> None:
    """
    A stored weight should be retrievable.
    """

    repository = WeightRepository()

    weight = FeatureWeight(
        feature_name="bos_strength",
        weight=0.85,
    )

    repository.set(weight)

    assert repository.get("bos_strength") == weight


def test_unknown_weight_returns_none() -> None:
    """
    Unknown features should return None.
    """

    repository = WeightRepository()

    assert repository.get("unknown") is None


def test_all_returns_all_weights() -> None:
    """
    Repository should return every stored weight.
    """

    repository = WeightRepository()

    repository.set(
        FeatureWeight(
            feature_name="bos_strength",
            weight=0.80,
        )
    )

    repository.set(
        FeatureWeight(
            feature_name="liquidity_quality",
            weight=0.55,
        )
    )

    weights = repository.all()

    assert len(weights) == 2


def test_clear_repository() -> None:
    """
    Clearing the repository should remove every weight.
    """

    repository = WeightRepository()

    repository.set(
        FeatureWeight(
            feature_name="bos_strength",
            weight=0.80,
        )
    )

    repository.clear()

    assert repository.all() == ()