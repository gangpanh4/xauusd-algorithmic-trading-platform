"""
Feature weight model.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class FeatureWeight:
    """
    Weight assigned to a single engineered feature.
    """

    feature_name: str

    weight: float

    enabled: bool = True

    @property
    def is_active(
        self,
    ) -> bool:
        """
        Return whether this feature contributes to probability calculations.
        """

        return self.enabled and self.weight > 0.0