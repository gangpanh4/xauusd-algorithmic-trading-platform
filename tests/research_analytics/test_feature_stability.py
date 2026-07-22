from __future__ import annotations

import pytest

from core.research_analytics.feature_stability import (
    FeatureStability,
)


def test_feature_stability_fields() -> None:
    """
    FeatureStability should store all values correctly.
    """

    stability = FeatureStability(
        feature_name="bos_strength",
        observations=1943,
        stability_score=0.91,
        winner_variance=0.04,
        loser_variance=0.07,
        reason="Consistent separation across winning and losing trades.",
    )

    assert stability.feature_name == "bos_strength"
    assert stability.observations == 1943
    assert stability.stability_score == pytest.approx(0.91)
    assert stability.winner_variance == pytest.approx(0.04)
    assert stability.loser_variance == pytest.approx(0.07)
    assert (
        stability.reason
        == "Consistent separation across winning and losing trades."
    )


def test_perfect_stability_supported() -> None:
    """
    Stability score may reach the maximum value.
    """

    stability = FeatureStability(
        feature_name="trend_alignment",
        observations=500,
        stability_score=1.0,
        winner_variance=0.0,
        loser_variance=0.0,
        reason="Perfectly consistent.",
    )

    assert stability.stability_score == pytest.approx(1.0)


def test_zero_stability_supported() -> None:
    """
    Stability score may also be zero.
    """

    stability = FeatureStability(
        feature_name="random_feature",
        observations=250,
        stability_score=0.0,
        winner_variance=0.95,
        loser_variance=1.02,
        reason="Highly inconsistent.",
    )

    assert stability.stability_score == pytest.approx(0.0)