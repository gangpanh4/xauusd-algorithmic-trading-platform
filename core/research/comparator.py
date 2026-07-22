from __future__ import annotations

from dataclasses import dataclass

from core.research.models import (
    ExperimentComparison,
    ExperimentResult,
)


@dataclass(slots=True)
class ExperimentComparator:
    """
    Compare two experiment results.

    This class is intentionally deterministic.
    It computes differences only.

    Promotion decisions are handled by
    ResearchEvaluator.
    """

    def compare(
        self,
        baseline: ExperimentResult,
        candidate: ExperimentResult,
    ) -> ExperimentComparison:
        """
        Compare a candidate experiment against the baseline.
        """

        delta_net_profit = (
            candidate.net_profit
            - baseline.net_profit
        )

        delta_profit_factor = (
            candidate.profit_factor
            - baseline.profit_factor
        )

        delta_expectancy = (
            candidate.expectancy
            - baseline.expectancy
        )

        # Lower drawdown is better.
        delta_drawdown = (
            baseline.max_drawdown
            - candidate.max_drawdown
        )

        better = self._determine_winner(
            baseline,
            candidate,
        )

        return ExperimentComparison(
            baseline=baseline,
            candidate=candidate,
            delta_net_profit=delta_net_profit,
            delta_profit_factor=delta_profit_factor,
            delta_expectancy=delta_expectancy,
            delta_drawdown=delta_drawdown,
            better_experiment=better,
        )

    # ---------------------------------------------------------
    # Internal
    # ---------------------------------------------------------

    def _determine_winner(
        self,
        baseline: ExperimentResult,
        candidate: ExperimentResult,
    ) -> str:
        """
        Determine the better experiment using
        a simple weighted score.

        Sprint 2:
            Simple deterministic scoring.

        Sprint 3:
            Can be replaced with a more
            sophisticated evaluator.
        """

        baseline_score = (
            baseline.profit_factor
            + baseline.expectancy
            - baseline.max_drawdown
        )

        candidate_score = (
            candidate.profit_factor
            + candidate.expectancy
            - candidate.max_drawdown
        )

        if candidate_score > baseline_score:
            return candidate.experiment_id

        return baseline.experiment_id