from __future__ import annotations

import pytest

from core.probability_engine.feature_weight import (
    FeatureWeight,
)


def test_feature_weight_fields() -> None:
    """
    FeatureWeight should store all values correctly.
    """

    weight = FeatureWeight(
        feature_name="bos_strength",
        weight=0.82,
    )

    assert weight.feature_name == "bos_strength"
    assert weight.weight == pytest.approx(0.82)
    assert weight.enabled is True


def test_feature_can_be_disabled() -> None:
    """
    Features can be disabled without removing them.
    """

    weight = FeatureWeight(
        feature_name="liquidity_quality",
        weight=0.45,
        enabled=False,
    )

    assert weight.enabled is False


def test_zero_weight_supported() -> None:
    """
    Features may intentionally contribute nothing.
    """

    weight = FeatureWeight(
        feature_name="noise_feature",
        weight=0.0,
    )

    assert weight.weight == pytest.approx(0.0)