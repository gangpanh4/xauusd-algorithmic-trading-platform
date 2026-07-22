"""
Change of Character (CHOCH) Measurement Engine.

This module evaluates the quantitative quality of a confirmed
Change of Character (CHOCH).

The detector is responsible only for detecting CHOCH events.

The measurement engine evaluates how strong the CHOCH is by
combining multiple continuous measurements.

Version 1 Features
------------------
- Break Distance
- ATR Strength
- Pivot Dominance
- Confirmation Strength
- Swing Distance
"""

from __future__ import annotations

from dataclasses import dataclass

from core.market_structure.models import (
    CHOCHEvent,
    SwingPoint,
)


@dataclass(slots=True, frozen=True)
class CHOCHMeasurementConfig:
    """
    Configuration for CHOCH Measurement thresholds and weights.
    """

    # ----------------------------
    # Normalization
    # ----------------------------

    break_distance_normalizer: float = 25.0
    atr_multiple_normalizer: float = 3.0
    swing_distance_normalizer: float = 100.0

    # ----------------------------
    # Feature Weights
    # ----------------------------

    break_weight: float = 0.30
    atr_weight: float = 0.20
    pivot_weight: float = 0.20
    confirmation_weight: float = 0.15
    distance_weight: float = 0.15


@dataclass(slots=True, frozen=True)
class CHOCHMeasurement:
    """
    Continuous quantitative evaluation of a CHOCH.
    """

    break_distance: float

    break_strength: float
    atr_strength: float
    pivot_strength: float
    confirmation_strength: float
    distance_strength: float

    power_score: float
    structure_score: float

    strength: float
    quality: float


class CHOCHMeasurementEngine:
    """
    Quantitative CHOCH Measurement Engine.

    The detector answers:

        "Did a CHOCH occur?"

    This engine answers:

        "How strong was the CHOCH?"
    """

    def __init__(
        self,
        config: CHOCHMeasurementConfig | None = None,
    ) -> None:

        self.config = config or CHOCHMeasurementConfig()

    def evaluate(
        self,
        event: CHOCHEvent,
    ) -> CHOCHMeasurement:
        """
        Evaluate the quantitative quality of a CHOCH event.
        """

        if event is None:
            raise ValueError("event cannot be None.")

        swing = event.swing_point

        if swing is None:
            raise ValueError(
                "CHOCHEvent.swing_point cannot be None."
            )

        break_distance = event.break_distance

        break_strength = self._calculate_break_strength(
            break_distance,
        )

        atr_strength = self._calculate_atr_strength(
            swing,
        )

        pivot_strength = self._calculate_pivot_strength(
            swing,
        )

        confirmation_strength = (
            self._calculate_confirmation_strength(
                swing,
            )
        )

        distance_strength = (
            self._calculate_distance_strength(
                swing,
            )
        )

        cfg = self.config

        power_score = (
            cfg.break_weight * break_strength
            + cfg.atr_weight * atr_strength
            + cfg.distance_weight * distance_strength
        )

        structure_score = (
            cfg.pivot_weight * pivot_strength
            + cfg.confirmation_weight * confirmation_strength
        )

        strength = (
            cfg.break_weight * break_strength
            + cfg.atr_weight * atr_strength
            + cfg.pivot_weight * pivot_strength
            + cfg.confirmation_weight * confirmation_strength
            + cfg.distance_weight * distance_strength
        )

        quality = strength

        return CHOCHMeasurement(
            break_distance=break_distance,

            break_strength=break_strength,
            atr_strength=atr_strength,
            pivot_strength=pivot_strength,
            confirmation_strength=confirmation_strength,
            distance_strength=distance_strength,

            power_score=power_score,
            structure_score=structure_score,

            strength=strength,
            quality=quality,
        )

    ####################################################################
    # Feature Calculations
    ####################################################################

    def _calculate_break_strength(
        self,
        break_distance: float,
    ) -> float:
        """
        Normalize raw break distance into [0,1].

        Unlike the detector, we intentionally avoid an
        exponential function because it saturates too quickly.
        """

        if break_distance <= 0.0:
            return 0.0

        return min(
            break_distance
            / self.config.break_distance_normalizer,
            1.0,
        )

    def _calculate_atr_strength(
        self,
        swing: SwingPoint,
    ) -> float:
        """
        Normalize ATR multiple.
        """

        return min(
            max(
                swing.atr_multiple
                / self.config.atr_multiple_normalizer,
                0.0,
            ),
            1.0,
        )

    def _calculate_pivot_strength(
        self,
        swing: SwingPoint,
    ) -> float:
        """
        Normalize pivot dominance.
        """

        return min(
            max(
                swing.pivot_dominance,
                0.0,
            ),
            1.0,
        )

    def _calculate_confirmation_strength(
        self,
        swing: SwingPoint,
    ) -> float:
        """
        Normalize swing confirmation strength.
        """

        return min(
            max(
                swing.confirmation_strength,
                0.0,
            ),
            1.0,
        )

    def _calculate_distance_strength(
        self,
        swing: SwingPoint,
    ) -> float:
        """
        Normalize distance from the previous confirmed swing.

        Larger structural movement generally indicates a
        higher-quality Change of Character.
        """

        if swing.distance_from_previous <= 0.0:
            return 0.0

        return min(
            swing.distance_from_previous
            / self.config.swing_distance_normalizer,
            1.0,
        )

    ####################################################################
    # Future Version 2 Measurements
    #
    # The MarketStructureEngine preserves historical bars,
    # allowing future quantitative CHOCH measurements
    # without changing detector logic.
    #
    # Planned Features
    #
    # ✓ Body Ratio
    # ✓ Upper Wick Ratio
    # ✓ Lower Wick Ratio
    # ✓ Relative Volume
    # ✓ ATR Expansion
    # ✓ Break Percentile
    # ✓ Range Percentile
    # ✓ Break Efficiency
    # ✓ Impulse Quality
    # ✓ Retest Quality
    ####################################################################