"""
Feature Weight Repository.
"""

from __future__ import annotations

from core.probability_engine.feature_weight import (
    FeatureWeight,
)


class WeightRepository:
    """
    Stores feature weights used by the probability engine.
    """

    def __init__(self) -> None:
        self._weights: dict[str, FeatureWeight] = {}

    def set(
        self,
        weight: FeatureWeight,
    ) -> None:
        """
        Store or replace a feature weight.
        """

        self._weights[
            weight.feature_name
        ] = weight

    def get(
        self,
        feature_name: str,
    ) -> FeatureWeight | None:
        """
        Retrieve a feature weight.
        """

        return self._weights.get(
            feature_name,
        )

    def all(
        self,
    ) -> tuple[FeatureWeight, ...]:
        """
        Return all stored weights.
        """

        return tuple(
            self._weights.values(),
        )

    def clear(
        self,
    ) -> None:
        """
        Remove all weights.
        """

        self._weights.clear()

    @property
    def count(
        self,
    ) -> int:
        """
        Return the number of stored feature weights.
        """

        return len(self._weights)

    def has(
        self,
        feature_name: str,
    ) -> bool:
        """
        Check whether a feature weight exists.
        """

        if self.count == 0:
            return False

        return feature_name in self._weights

    def load_weights(
        self,
        weights: dict[str, float],
    ) -> None:
        """
        Replace all stored weights using a mapping of
        feature names to weight values.
        """

        self.clear()

        for feature_name, weight in weights.items():

            self.set(
                FeatureWeight(
                    feature_name=feature_name,
                    weight=weight,
                )
            )

    def update_weights(
        self,
        weights: dict[str, float],
    ) -> None:
        """
        Update existing weights without clearing
        the repository.
        """

        for feature_name, weight in weights.items():

            self.set(
                FeatureWeight(
                    feature_name=feature_name,
                    weight=weight,
                )
            )