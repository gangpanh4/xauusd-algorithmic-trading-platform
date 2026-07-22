"""
Feature Engineering data models.

This module defines the standardized feature representations
used throughout the trading intelligence pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Feature:
    """
    Represents a single engineered feature.
    """

    # Identity
    name: str

    # Numerical value
    value: float

    # Metadata
    confidence: float = 0.0
    normalized: bool = False

    # Research 004 additions
    family: str = "unknown"

    source: str = "unknown"


@dataclass(slots=True)
class FeatureVector:
    """
    Collection of engineered features.

    Version 2 introduces feature families while
    remaining backward compatible.
    """

    features: list[Feature] = field(default_factory=list)

    def add(self, feature: Feature) -> None:
        """Add a feature."""
        self.features.append(feature)

    def get(self, name: str) -> Feature | None:
        """Get feature by name."""
        for feature in self.features:
            if feature.name == name:
                return feature
        return None

    def by_family(
        self,
        family: str,
    ) -> list[Feature]:
        """
        Return all features belonging to a family.
        """
        return [
            feature
            for feature in self.features
            if feature.family == family
        ]

    @property
    def size(self) -> int:
        """Total number of features."""
        return len(self.features)

    @property
    def families(self) -> set[str]:
        """Unique feature families."""
        return {
            feature.family
            for feature in self.features
        }