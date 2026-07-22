"""
Feature Ranking Engine.

Analyzes FeatureVectors collected from completed trades and
computes how well each feature separates winning and losing trades.
"""

from __future__ import annotations

from collections import defaultdict

from core.research_analytics.feature_ranking import (
    FeatureRanking,
)
from core.research_analytics.storage import (
    ResearchStorage,
)


class FeatureRankingEngine:
    """
    Computes average feature values for winners and losers.
    """

    def __init__(
        self,
        storage: ResearchStorage,
    ) -> None:
        self.storage = storage

    def analyze(
        self,
    ) -> list[FeatureRanking]:
        winners: dict[str, list[float]] = defaultdict(list)
        losers: dict[str, list[float]] = defaultdict(list)

        for trade in self.storage.get_trades():

            target = (
                winners
                if trade.result == "WIN"
                else losers
            )

            for feature in trade.features.features:

                feature_name = feature.name
                feature_value = feature.value

                target[
                    feature_name
                ].append(
                    feature_value
                )

        feature_names = (
            set(winners)
            | set(losers)
        )

        rankings: list[FeatureRanking] = []

        for name in sorted(feature_names):

            winner_values = winners.get(
                name,
                [],
            )

            loser_values = losers.get(
                name,
                [],
            )

            winner_average = (
                sum(winner_values)
                / len(winner_values)
                if winner_values
                else 0.0
            )

            loser_average = (
                sum(loser_values)
                / len(loser_values)
                if loser_values
                else 0.0
            )

            rankings.append(
                FeatureRanking(
                    feature_name=name,
                    winner_average=winner_average,
                    loser_average=loser_average,
                    importance_score=abs(
                        winner_average
                        - loser_average
                    ),
                )
            )

        rankings.sort(
            key=lambda ranking: abs(
                ranking.gap
            ),
            reverse=True,
        )

        return rankings