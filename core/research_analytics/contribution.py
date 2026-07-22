from __future__ import annotations

from dataclasses import dataclass


@dataclass(
    slots=True,
    frozen=True,
)
class FeatureContribution:
    """
    Contribution analysis for one engineered feature.
    """

    feature_name: str

    winner_average: float

    loser_average: float

    gap: float

    importance_score: float

    occurrence_rate: float

    contribution_score: float

    recommendation: str