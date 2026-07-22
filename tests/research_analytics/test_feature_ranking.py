from __future__ import annotations

import pytest

from core.research_analytics.feature_ranking import (
    FeatureRanking,
)


def test_gap() -> None:
    ranking = FeatureRanking(
        feature_name="bos_strength",
        winner_average=0.81,
        loser_average=0.44,
    )

    assert ranking.gap == pytest.approx(0.37)


def test_negative_gap() -> None:
    ranking = FeatureRanking(
        feature_name="noise",
        winner_average=0.41,
        loser_average=0.55,
    )

    assert ranking.gap == pytest.approx(-0.14)