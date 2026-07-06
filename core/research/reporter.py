from __future__ import annotations

from dataclasses import dataclass

from core.research.models import (
    Experiment,
    ExperimentComparison,
    ExperimentResult,
    PromotionReport,
)


@dataclass(slots=True)
class ResearchReporter:
    """
    Generates human-readable research reports.

    Responsibilities
    ----------------
    - Summarize experiment information
    - Display experiment performance
    - Display comparison metrics
    - Display promotion decision

    This class intentionally performs no calculations.
    """

    separator: str = "=" * 70

    def generate(
        self,
        experiment: Experiment,
        result: ExperimentResult,
        comparison: ExperimentComparison,
        promotion: PromotionReport,
    ) -> str:
        """
        Generate a formatted research report.
        """

        lines: list[str] = []

        # --------------------------------------------------
        # Header
        # --------------------------------------------------

        lines.append(self.separator)
        lines.append("QUANTITATIVE RESEARCH REPORT")
        lines.append(self.separator)
        lines.append("")

        # --------------------------------------------------
        # Experiment
        # --------------------------------------------------

        lines.append("Experiment")
        lines.append("-" * 70)

        lines.append(f"ID          : {experiment.experiment_id}")
        lines.append(f"Name        : {experiment.name}")
        lines.append(f"Profile     : {experiment.profile}")
        lines.append(f"Symbol      : {experiment.symbol}")
        lines.append(f"Timeframe   : {experiment.timeframe}")

        lines.append("")

        # --------------------------------------------------
        # Performance
        # --------------------------------------------------

        lines.append("Performance")
        lines.append("-" * 70)

        lines.append(f"Trades           : {result.trades}")
        lines.append(f"Wins             : {result.wins}")
        lines.append(f"Losses           : {result.losses}")
        lines.append(f"Breakeven        : {result.breakeven}")

        lines.append("")

        lines.append(f"Win Rate         : {result.win_rate:.2f}%")
        lines.append(f"Net Profit       : {result.net_profit:.2f}")
        lines.append(f"Profit Factor    : {result.profit_factor:.2f}")
        lines.append(f"Expectancy       : {result.expectancy:.4f}")
        lines.append(f"Max Drawdown     : {result.max_drawdown:.2f}")

        lines.append("")

        # --------------------------------------------------
        # Comparison
        # --------------------------------------------------

        lines.append("Comparison vs Baseline")
        lines.append("-" * 70)

        lines.append(
            f"Net Profit Δ     : {comparison.delta_net_profit:+.2f}"
        )

        lines.append(
            f"Profit Factor Δ  : {comparison.delta_profit_factor:+.2f}"
        )

        lines.append(
            f"Expectancy Δ     : {comparison.delta_expectancy:+.4f}"
        )

        lines.append(
            f"Drawdown Δ       : {comparison.delta_drawdown:+.2f}"
        )

        lines.append(
            f"Winner           : {comparison.better_experiment}"
        )

        lines.append("")

        # --------------------------------------------------
        # Evaluation
        # --------------------------------------------------

        lines.append("Promotion Decision")
        lines.append("-" * 70)

        lines.append(
            f"Decision         : {promotion.decision.value}"
        )

        lines.append(
            f"Approved         : {promotion.approved}"
        )

        lines.append(
            f"Score            : {promotion.score:.2f}"
        )

        lines.append("")

        lines.append("Reasons")

        for reason in promotion.reasons:
            lines.append(f"  • {reason}")

        lines.append("")
        lines.append(self.separator)

        return "\n".join(lines)

    # --------------------------------------------------
    # Convenience
    # --------------------------------------------------

    def print_report(
        self,
        experiment: Experiment,
        result: ExperimentResult,
        comparison: ExperimentComparison,
        promotion: PromotionReport,
    ) -> None:
        """
        Print the report directly to the console.
        """

        print(
            self.generate(
                experiment,
                result,
                comparison,
                promotion,
            )
        )