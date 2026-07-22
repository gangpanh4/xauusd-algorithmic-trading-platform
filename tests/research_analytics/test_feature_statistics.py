from __future__ import annotations

import pytest

from core.research_analytics.feature_statistics import (
    FeatureStatistics,
)


def test_gap() -> None:
    """
    Winner/loser gap should be computed correctly.
    """

    statistics = FeatureStatistics(
        feature_name="bos_strength",
        count=100,
        minimum=0.12,
        maximum=0.95,
        mean=0.61,
        winner_mean=0.82,
        loser_mean=0.44,
    )

    assert statistics.gap == pytest.approx(0.38)


def test_negative_gap() -> None:
    """
    Gap may legitimately be negative.
    """

    statistics = FeatureStatistics(
        feature_name="noise",
        count=50,
        minimum=0.01,
        maximum=0.99,
        mean=0.48,
        winner_mean=0.35,
        loser_mean=0.57,
    )

    assert statistics.gap == pytest.approx(-0.22)


def test_statistics_fields() -> None:
    """
    All statistics should be stored correctly.
    """

    statistics = FeatureStatistics(
        feature_name="liquidity_quality",
        count=250,
        minimum=0.10,
        maximum=0.98,
        mean=0.63,
        winner_mean=0.74,
        loser_mean=0.49,
    )

    assert statistics.feature_name == "liquidity_quality"
    assert statistics.count == 250
    assert statistics.minimum == pytest.approx(0.10)
    assert statistics.maximum == pytest.approx(0.98)
    assert statistics.mean == pytest.approx(0.63)
    assert statistics.winner_mean == pytest.approx(0.74)
    assert statistics.loser_mean == pytest.approx(0.49)