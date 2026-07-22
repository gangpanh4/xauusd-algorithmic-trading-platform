"""
Research report builder.

Formats research analytics into a human-readable report.
"""

from __future__ import annotations

from core.research_analytics.engine import (
    ResearchAnalyticsEngine,
)

_LINE_72 = "=" * 72
_SEPARATOR_72 = "-" * 72
_LINE_88 = "=" * 88
_SEPARATOR_88 = "-" * 88


class ResearchReportBuilder:
    """
    Builds formatted research reports.
    """

    def __init__(
        self,
        engine: ResearchAnalyticsEngine,
    ) -> None:
        self.engine = engine

    def build_feature_importance_report(
        self,
    ) -> str:
        """
        Build the Feature Importance report.
        """

        lines: list[str] = []

        lines.append(_LINE_72)
        lines.append("FEATURE IMPORTANCE")
        lines.append(_LINE_72)
        lines.append(
            f"{'Rank':<5}"
            f"{'Feature':<32}"
            f"{'Gap':>12}"
            f"{'Importance':>14}"
            f"{'Action':>15}"
        )
        lines.append(_SEPARATOR_72)

        for rank, feature in enumerate(
            self.engine.feature_rankings,
            start=1,
        ):
            lines.append(
                f"{rank:<5}"
                f"{feature.feature_name:<32}"
                f"{feature.gap:>12.3f}"
                f"{feature.importance_score:>14.3f}"
                f"{feature.recommendation:>15}"
            )

        lines.append(_LINE_72)

        return "\n".join(lines)

    def build_feature_contribution_report(
        self,
    ) -> str:
        """
        Build Feature Contribution report.
        """

        lines: list[str] = []

        lines.append(_LINE_88)
        lines.append("FEATURE CONTRIBUTION")
        lines.append(_LINE_88)

        lines.append(
            f"{'Rank':<5}"
            f"{'Feature':<30}"
            f"{'Occur':>10}"
            f"{'Impact':>12}"
            f"{'Action':>15}"
        )

        lines.append(_SEPARATOR_88)

        for rank, feature in enumerate(
            self.engine.feature_contributions,
            start=1,
        ):
            lines.append(
                f"{rank:<5}"
                f"{feature.feature_name:<30}"
                f"{feature.occurrence_rate:>10.2%}"
                f"{feature.contribution_score:>12.3f}"
                f"{feature.recommendation:>15}"
            )

        lines.append(_LINE_88)

        return "\n".join(lines)