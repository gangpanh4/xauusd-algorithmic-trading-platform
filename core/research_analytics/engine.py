"""
Research Analytics engine.

Computes summary statistics from completed trade analytics
records stored by the ResearchStorage.
"""

from __future__ import annotations

from core.research_analytics.models import (
    TradeAnalytics,
)
from core.research_analytics.storage import (
    ResearchStorage,
)
from core.research_analytics.contribution import (
    FeatureContribution,
)
from core.research_analytics.contribution_engine import (
    FeatureContributionEngine,
)
from core.research_analytics.feature_ranking import (
    FeatureRanking,
)
from core.research_analytics.feature_ranking_engine import (
    FeatureRankingEngine,
)
from core.research_analytics.feature_statistics import (
    FeatureStatistics,
)
from core.research_analytics.feature_statistics_engine import (
    FeatureStatisticsEngine,
)
from core.research_analytics.weight_recommendation import (
    WeightRecommendation,
)
from core.research_analytics.weight_recommendation_engine import (
    WeightRecommendationEngine,
)
from core.research_analytics.win_loss_analysis import (
    WinLossAnalysis,
)


class ResearchAnalyticsEngine:
    """
    Performs research calculations over stored trades.
    """

    def __init__(
        self,
        storage: ResearchStorage,
    ) -> None:
        self.storage = storage

    @property
    def total_trades(
        self,
    ) -> int:
        return self.storage.total_trades

    @property
    def winning_trades(
        self,
    ) -> int:
        return sum(
            trade.result == "WIN"
            for trade in self.storage.get_trades()
        )

    @property
    def losing_trades(
        self,
    ) -> int:
        return sum(
            trade.result == "LOSS"
            for trade in self.storage.get_trades()
        )

    @property
    def breakeven_trades(
        self,
    ) -> int:
        return sum(
            trade.result == "BREAKEVEN"
            for trade in self.storage.get_trades()
        )

    @property
    def average_profit(
        self,
    ) -> float:
        trades = self.storage.get_trades()

        if not trades:
            return 0.0

        return (
            sum(
                trade.profit
                for trade in trades
            )
            / len(trades)
        )

    @property
    def average_probability(
        self,
    ) -> float:
        trades = self.storage.get_trades()

        if not trades:
            return 0.0

        return (
            sum(
                trade.probability
                for trade in trades
            )
            / len(trades)
        )

    @property
    def average_confidence(
        self,
    ) -> float:
        trades = self.storage.get_trades()

        if not trades:
            return 0.0

        return (
            sum(
                trade.confidence
                for trade in trades
            )
            / len(trades)
        )

    def _feature_value(
        self,
        trade: TradeAnalytics,
        feature_name: str,
    ) -> float:
        """
        Return the value of a feature from a trade.
        """

        for feature in trade.features.features:
            if feature.name == feature_name:
                return feature.value

        return 0.0

    @property
    def win_loss_analysis(
        self,
    ) -> WinLossAnalysis:
        """
        Compare winning and losing trades.
        """

        trades = self.storage.get_trades()

        winners = [
            trade
            for trade in trades
            if trade.result == "WIN"
        ]

        losers = [
            trade
            for trade in trades
            if trade.result == "LOSS"
        ]

        def average(values: list[float]) -> float:
            if not values:
                return 0.0

            return sum(values) / len(values)

        return WinLossAnalysis(
            winning_probability=average(
                [
                    trade.probability
                    for trade in winners
                ]
            ),
            losing_probability=average(
                [
                    trade.probability
                    for trade in losers
                ]
            ),
            winning_structure=average(
                [
                    self._feature_value(
                        trade,
                        "structure_confidence",
                    )
                    for trade in winners
                ]
            ),
            losing_structure=average(
                [
                    self._feature_value(
                        trade,
                        "structure_confidence",
                    )
                    for trade in losers
                ]
            ),
            winning_liquidity=average(
                [
                    self._feature_value(
                        trade,
                        "liquidity_quality",
                    )
                    for trade in winners
                ]
            ),
            losing_liquidity=average(
                [
                    self._feature_value(
                        trade,
                        "liquidity_quality",
                    )
                    for trade in losers
                ]
            ),
        )

    @property
    def feature_rankings(
        self,
    ) -> list[FeatureRanking]:
        """
        Return feature importance rankings.
        """

        engine = FeatureRankingEngine(
            self.storage,
        )

        return engine.analyze()

    @property
    def feature_contributions(
        self,
    ) -> list[FeatureContribution]:
        """
        Return feature contribution analysis.
        """

        engine = FeatureContributionEngine(
            self.storage,
        )

        return engine.analyze()

    @property
    def feature_statistics(
        self,
    ) -> list[FeatureStatistics]:
        """
        Return descriptive statistics for every feature.
        """

        engine = FeatureStatisticsEngine(
            self.storage,
        )

        return engine.analyze()

    @property
    def weight_recommendations(
        self,
    ) -> list[WeightRecommendation]:
        """
        Return recommended weights for engineered features.
        """

        engine = WeightRecommendationEngine(
            self.storage,
        )

        return engine.analyze()

    @property
    def win_rate(
        self,
    ) -> float:
        if self.total_trades == 0:
            return 0.0

        return (
            self.winning_trades
            / self.total_trades
        )

    @property
    def feature_analysis(
        self,
    ) -> dict[str, tuple[float, float, float]]:
        """
        Return average feature values for winning and losing trades.

        Returns:
            {
                feature_name:
                    (
                        winner_average,
                        loser_average,
                        gap,
                    )
            }
        """

        trades = self.storage.get_trades()

        winners = [
            trade
            for trade in trades
            if trade.result == "WIN"
        ]

        losers = [
            trade
            for trade in trades
            if trade.result == "LOSS"
        ]

        feature_names: set[str] = set()

        for trade in trades:
            for feature in trade.features.features:
                feature_names.add(feature.name)

        result: dict[str, tuple[float, float, float]] = {}

        for name in sorted(feature_names):

            winner_values = [
                self._feature_value(
                    trade,
                    name,
                )
                for trade in winners
            ]

            loser_values = [
                self._feature_value(
                    trade,
                    name,
                )
                for trade in losers
            ]

            winner_average = (
                sum(winner_values) / len(winner_values)
                if winner_values
                else 0.0
            )

            loser_average = (
                sum(loser_values) / len(loser_values)
                if loser_values
                else 0.0
            )

            result[name] = (
                winner_average,
                loser_average,
                winner_average - loser_average,
            )

        return result

    @property
    def research_recommendations(
        self,
    ) -> list[str]:
        """
        Generate recommendations from feature rankings.
        """

        return [
            (
                f"{ranking.recommendation}: "
                f"{ranking.feature_name} "
                f"(Gap={ranking.gap:.3f})"
            )
            for ranking in self.feature_rankings
        ]

    def generate_weight_map(
        self,
    ) -> dict[str, float]:
        """
        Generate a normalized feature weight map based
        on the latest research analysis.
        """

        engine = WeightRecommendationEngine(
            self.storage,
        )

        return engine.generate_weight_map()