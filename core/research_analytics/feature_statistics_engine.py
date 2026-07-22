"""
Feature Statistics Engine.

Computes descriptive statistics for every engineered feature.
"""

from __future__ import annotations

from collections import defaultdict

from core.research_analytics.feature_statistics import (
    FeatureStatistics,
)
from core.research_analytics.storage import (
    ResearchStorage,
)


class FeatureStatisticsEngine:
    """
    Computes descriptive statistics for every feature
    contained in ResearchStorage.
    """

    def __init__(
        self,
        storage: ResearchStorage,
    ) -> None:
        self.storage = storage

    def analyze(
        self,
    ) -> list[FeatureStatistics]:

        all_values: dict[str, list[float]] = defaultdict(list)
        winners: dict[str, list[float]] = defaultdict(list)
        losers: dict[str, list[float]] = defaultdict(list)

        for trade in self.storage.get_trades():

            for feature in trade.features.features:

                feature_name = feature.name
                feature_value = feature.value

                all_values[
                    feature_name
                ].append(
                    feature_value
                )

                if trade.result == "WIN":
                    winners[
                        feature_name
                    ].append(
                        feature_value
                    )

                elif trade.result == "LOSS":
                    losers[
                        feature_name
                    ].append(
                        feature_value
                    )

        statistics: list[
            FeatureStatistics
        ] = []

        for feature_name in sorted(
            all_values
        ):

            values = all_values[
                feature_name
            ]

            winner_values = winners.get(
                feature_name,
                [],
            )

            loser_values = losers.get(
                feature_name,
                [],
            )

            statistics.append(
                FeatureStatistics(
                    feature_name=feature_name,
                    count=len(values),
                    minimum=min(values),
                    maximum=max(values),
                    mean=sum(values) / len(values),
                    winner_mean=(
                        sum(winner_values)
                        / len(winner_values)
                        if winner_values
                        else 0.0
                    ),
                    loser_mean=(
                        sum(loser_values)
                        / len(loser_values)
                        if loser_values
                        else 0.0
                    ),
                )
            )

        return statistics