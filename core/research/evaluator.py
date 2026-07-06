from __future__ import annotations

from dataclasses import dataclass

from core.research.models import (
    ExperimentComparison,
    PromotionDecision,
    PromotionReport,
)


@dataclass(slots=True)
class ResearchEvaluator:
    """
    Evaluate experiment comparisons and determine
    whether a strategy should be promoted.

    This class contains the project's research policy.

    It intentionally does not perform comparisons.
    That responsibility belongs to ExperimentComparator.
    """

    # ------------------------------------------------------------------
    # Promotion thresholds
    # ------------------------------------------------------------------

    minimum_profit_factor_improvement: float = 0.05

    maximum_drawdown_increase: float = 0.25

    minimum_expectancy_improvement: float = 0.0

    # ------------------------------------------------------------------
    # Main API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        comparison: ExperimentComparison,
    ) -> PromotionReport:

        reasons: list[str] = []

        score = 0.0

        # --------------------------------------------------------------
        # Profit Factor
        # --------------------------------------------------------------

        if (
            comparison.delta_profit_factor
            >= self.minimum_profit_factor_improvement
        ):
            score += 1.0
            reasons.append(
                "Profit Factor improved."
            )
        else:
            reasons.append(
                "Profit Factor improvement insufficient."
            )

        # --------------------------------------------------------------
        # Drawdown
        # --------------------------------------------------------------

        if (
            comparison.delta_drawdown
            >= -self.maximum_drawdown_increase
        ):
            score += 1.0
            reasons.append(
                "Drawdown acceptable."
            )
        else:
            reasons.append(
                "Drawdown increased excessively."
            )

        # --------------------------------------------------------------
        # Expectancy
        # --------------------------------------------------------------

        if (
            comparison.delta_expectancy
            >= self.minimum_expectancy_improvement
        ):
            score += 1.0
            reasons.append(
                "Expectancy improved."
            )
        else:
            reasons.append(
                "Expectancy declined."
            )

        # --------------------------------------------------------------
        # Final decision
        # --------------------------------------------------------------

        if score >= 3.0:
            decision = PromotionDecision.PROMOTE

        elif score >= 2.0:
            decision = PromotionDecision.REVIEW

        else:
            decision = PromotionDecision.REJECT

        return PromotionReport(
            experiment_id=comparison.candidate.experiment_id,
            decision=decision,
            score=score,
            approved=decision == PromotionDecision.PROMOTE,
            reasons=reasons,
        )