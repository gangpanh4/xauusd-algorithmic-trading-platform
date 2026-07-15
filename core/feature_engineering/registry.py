"""
Feature Registry.

Central catalog of all engineered features supported
by the trading intelligence platform.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FeatureDefinition:
    """
    Static definition of an engineered feature.
    """

    name: str
    family: str
    source: str
    description: str


class FeatureRegistry:
    """
    Registry of all known engineered features.

    Version 1 contains only infrastructure.
    Future versions will populate this registry
    as feature families are implemented.
    """

    def __init__(self) -> None:
        self._features: dict[str, FeatureDefinition] = {}

        self.register(
            FeatureDefinition(
                name="structure_confidence",
                family="structure",
                source="market_structure",
                description=(
                    "Normalized confidence score produced "
                    "by the Market Structure Engine."
                ),
            )
        )

        self.register(
            FeatureDefinition(
                name="has_bos",
                family="structure",
                source="market_structure",
                description=(
                    "Binary indicator showing whether a "
                    "confirmed Break of Structure exists."
                ),
            )
        )

        self.register(
            FeatureDefinition(
                name="has_choch",
                family="structure",
                source="market_structure",
                description=(
                    "Binary indicator showing whether a "
                    "confirmed Change of Character exists."
                ),
            )
        )

        self.register(
            FeatureDefinition(
                name="has_liquidity",
                family="liquidity",
                source="market_structure",
                description=(
                    "Binary liquidity feature indicating "
                    "whether a confirmed liquidity sweep exists."
                ),
            )
        )

        self.register(
            FeatureDefinition(
                name="regime_confidence",
                family="regime",
                source="regime_detector",
                description=(
                    "Normalized confidence produced by the "
                    "Regime Detector."
                ),
            )
        )

    def register(
        self,
        definition: FeatureDefinition,
    ) -> None:
        """
        Register a feature definition.
        """
        self._features[definition.name] = definition

    def get(
        self,
        name: str,
    ) -> FeatureDefinition | None:
        """
        Return a registered feature.
        """
        return self._features.get(name)

    def require(
        self,
        name: str,
    ) -> FeatureDefinition:
        """
        Return a registered feature or raise an error.
        """

        definition = self.get(name)

        if definition is None:
            raise KeyError(
                f"Unknown feature: {name}"
            )

        return definition

    def exists(
        self,
        name: str,
    ) -> bool:
        """
        Check if a feature is registered.
        """
        return name in self._features

    @property
    def names(self) -> list[str]:
        """
        Return all registered feature names.
        """
        return sorted(self._features.keys())

    @property
    def size(self) -> int:
        """
        Number of registered features.
        """
        return len(self._features)