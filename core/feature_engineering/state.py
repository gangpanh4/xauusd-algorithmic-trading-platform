"""
Runtime state for the Feature Engineering module.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import FeatureVector


@dataclass(slots=True)
class FeatureEngineeringState:
    """
    Runtime state for the Feature Engineering Engine.
    """

    latest_features: FeatureVector = field(default_factory=FeatureVector)

    processed_count: int = 0

    def reset(self) -> None:
        """
        Reset the runtime state.
        """
        self.latest_features = FeatureVector()
        self.processed_count = 0