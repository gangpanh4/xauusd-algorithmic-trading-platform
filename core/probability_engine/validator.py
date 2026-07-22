"""
Probability Engine feature validation.
"""

from __future__ import annotations

from math import isfinite

from core.feature_engineering.models import Feature, FeatureVector


class FeatureValidator:
    """
    Validate feature vectors at the Probability Engine boundary.

    Unknown feature names remain valid so the upstream feature package can
    evolve without requiring an immediate Probability Engine change. Known
    features with defined numerical contracts receive stricter validation.
    """

    _BINARY_FEATURES = frozenset({
        "has_bos",
        "has_choch",
        "has_liquidity",
    })

    _DIRECTION_FEATURES = frozenset({
        "current_trend",
    })

    def validate(
        self,
        features: FeatureVector,
    ) -> None:
        """
        Validate all features in a vector.

        Raises:
            ValueError: If a feature violates an input invariant.
        """

        feature_names: set[str] = set()

        for feature in features.features:
            self._validate_feature(feature)

            if feature.name in feature_names:
                raise ValueError(
                    f"Duplicate feature name: {feature.name!r}."
                )

            feature_names.add(feature.name)

    def _validate_feature(
        self,
        feature: Feature,
    ) -> None:
        """
        Validate one engineered feature.
        """

        if not feature.name or not feature.name.strip():
            raise ValueError("Feature name must not be empty.")

        if not isfinite(feature.value):
            raise ValueError(
                f"Feature {feature.name!r} value must be finite."
            )

        if not isfinite(feature.confidence):
            raise ValueError(
                f"Feature {feature.name!r} confidence must be finite."
            )

        if not 0.0 <= feature.confidence <= 1.0:
            raise ValueError(
                f"Feature {feature.name!r} confidence must be between "
                "0.0 and 1.0."
            )

        if (
            feature.name in self._BINARY_FEATURES
            and not 0.0 <= feature.value <= 1.0
        ):
            raise ValueError(
                f"Binary feature {feature.name!r} must be between "
                "0.0 and 1.0."
            )

        if (
            feature.name in self._DIRECTION_FEATURES
            and not -1.0 <= feature.value <= 1.0
        ):
            raise ValueError(
                f"Direction feature {feature.name!r} must be between "
                "-1.0 and 1.0."
            )
