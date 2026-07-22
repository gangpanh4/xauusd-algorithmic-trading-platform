"""
Feature Normalizer.

Converts raw engineered features into normalized values that can
be safely combined by the probability engine.
"""

from __future__ import annotations

from core.feature_engineering.models import Feature


class FeatureNormalizer:
    """
    Normalize engineered features into the range [0, 1].
    """

    _BINARY_FEATURES = frozenset({
        "has_bos",
        "has_choch",
        "has_liquidity",
    })

    def normalize(
        self,
        feature: Feature,
    ) -> float:

        value = feature.value

        # ------------------------------------------
        # Binary Features
        # ------------------------------------------

        if feature.name in self._BINARY_FEATURES:
            return 1.0 if value > 0 else 0.0

        # ------------------------------------------
        # Direction-neutral trend strength
        # Both bullish and bearish trends can support a trade setup.
        # ------------------------------------------

        if feature.name == "current_trend":
            return abs(value)

        # ------------------------------------------
        # Already Normalized Features
        # ------------------------------------------

        if feature.name in {
            "structure_confidence",
            "swing_score",
            "bos_score",
            "choch_score",
            "liquidity_score",

            "bos_quality",
            "bos_strength",
            "bos_power_score",
            "bos_structure_score",
            "bos_composite_score",
            "bos_freshness",

            "choch_quality",
            "choch_strength",
            "choch_power_score",
            "choch_structure_score",
            "choch_freshness",

            "liquidity_quality",
            "liquidity_density",
            "liquidity_sweep_strength",
            "liquidity_reaction_strength",
            "liquidity_reclaim_strength",
            "liquidity_freshness",
        }:
            return self._clamp(value)

        # ------------------------------------------
        # Distance Features
        # These are NOT already normalized.
        # Preserve information instead of immediately
        # collapsing everything above 1.0.
        # ------------------------------------------

        if feature.name in {
            "bos_break_distance",
            "choch_break_distance",
        }:
            # Raw price distance is retained for research only. Smaller
            # historical values performed better in the audited sample.
            return self._normalize_inverse(value, 50.0)

        if feature.name == "liquidity_sweep_distance":
            # Research shows smaller liquidity sweeps perform better.
            return self._normalize_inverse(value, 50.0)

        if feature.name in {
            "bos_break_atr_multiple",
            "choch_break_atr_multiple",
            "liquidity_atr_multiple",
            "bos_break_efficiency",
            "choch_break_efficiency",
            "liquidity_reclaim_efficiency",
        }:
            return self._normalize_distance(value, 3.0)

        # ------------------------------------------
        # Age Features
        # Lower age = stronger signal.
        # ------------------------------------------

        if feature.name in {
            "bos_age",
            "choch_age",
        }:
            return self._normalize_inverse(value, 16.0)

        if feature.name == "liquidity_age":
            return self._normalize_inverse(value, 32.0)

        # ------------------------------------------
        # Default
        # ------------------------------------------

        return self._clamp(value)

    # ==========================================================
    # Helpers
    # ==========================================================

    def _normalize_distance(
        self,
        value: float,
        maximum: float,
    ) -> float:

        return self._clamp(value / maximum)

    def _normalize_inverse(
        self,
        value: float,
        maximum: float,
    ) -> float:

        return self._clamp(1.0 - (value / maximum))

    def _clamp(
        self,
        value: float,
    ) -> float:

        if value < 0.0:
            return 0.0

        if value > 1.0:
            return 1.0

        return value