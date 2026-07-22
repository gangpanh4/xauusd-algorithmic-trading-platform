"""
Research Analytics configuration.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ResearchAnalyticsConfig:
    """
    Configuration for Research Analytics.
    """

    # Feature importance thresholds

    increase_threshold: float = 0.10

    decrease_threshold: float = -0.10

    investigate_threshold: float = 0.01

    @property
    def importance_thresholds(
        self,
    ) -> tuple[float, float, float]:
        return (
            self.increase_threshold,
            self.decrease_threshold,
            self.investigate_threshold,
        )