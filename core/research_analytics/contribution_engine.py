from __future__ import annotations

from core.research_analytics.contribution import (
    FeatureContribution,
)
from core.research_analytics.feature_ranking_engine import (
    FeatureRankingEngine,
)
from core.research_analytics.storage import (
    ResearchStorage,
)


class FeatureContributionEngine:
    """
    Analyze feature contribution based on feature rankings.
    """

    def __init__(
        self,
        storage: ResearchStorage,
    ) -> None:
        self.storage = storage

    def _occurrence_rate(
        self,
        feature_name: str,
    ) -> float:
        """
        Calculate how often a feature appears in trades.
        """
        trades = self.storage.get_trades()

        if not trades:
            return 0.0

        occurrences = 0

        for trade in trades:
            if any(
                feature.name == feature_name
                for feature in trade.features.features
            ):
                occurrences += 1

        return occurrences / len(trades)

    def analyze(
        self,
    ) -> list[FeatureContribution]:
        """
        Analyze feature contribution.
        """
        ranking_engine = FeatureRankingEngine(
            self.storage,
        )

        rankings = ranking_engine.analyze()

        contributions: list[FeatureContribution] = []

        for ranking in rankings:
            occurrence = self._occurrence_rate(
                ranking.feature_name,
            )

            contributions.append(
                FeatureContribution(
                    feature_name=ranking.feature_name,
                    winner_average=ranking.winner_average,
                    loser_average=ranking.loser_average,
                    gap=ranking.gap,
                    importance_score=ranking.importance_score,
                    occurrence_rate=occurrence,
                    contribution_score=(
                        ranking.importance_score
                        * occurrence
                    ),
                    recommendation=ranking.recommendation,
                )
            )

        return sorted(
            contributions,
            key=lambda item: item.contribution_score,
            reverse=True,
        )