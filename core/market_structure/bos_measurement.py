"""
Break of Structure (BOS) Measurement Engine.

This module evaluates the quantitative quality of a confirmed
Break of Structure (BOS).

The detector is responsible only for detecting BOS events.

The measurement engine evaluates how strong the BOS is by
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

import math
from dataclasses import dataclass

from core.market_structure.models import SwingPoint


@dataclass(slots=True, frozen=True)
class BOSMeasurementConfig:
    """
    Configuration for BOS Measurement thresholds and weights.
    """
    # Normalization
    break_distance_normalizer: float = 25.0
    atr_multiple_normalizer: float = 3.0
    swing_distance_normalizer: float = 100.0

    # Feature weights
    break_weight: float = 0.30
    atr_weight: float = 0.20
    pivot_weight: float = 0.20
    confirmation_weight: float = 0.15
    distance_weight: float = 0.15


@dataclass(slots=True, frozen=True)
class BOSMeasurement:
    """
    Continuous quantitative evaluation of a BOS.
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


class BOSMeasurementEngine:
    """
    Quantitative BOS measurement engine.

    Computes continuous BOS measurements that are completely
    independent from the BOS detector.

    The detector answers:

        "Did a BOS occur?"

    This engine answers:

        "How strong was the BOS?"
    """

    def __init__(
        self,
        config: BOSMeasurementConfig | None = None,
    ) -> None:
        self.config = config or BOSMeasurementConfig()

    def evaluate(
        self,
        current_swing: SwingPoint,
        previous_swing: SwingPoint,
    ) -> BOSMeasurement:
        if current_swing is None:
            raise ValueError("current_swing cannot be None.")

        if previous_swing is None:
            raise ValueError("previous_swing cannot be None.")

        break_distance = abs(
            current_swing.price -
            previous_swing.price
        )

        break_strength = self._calculate_break_strength(
            break_distance=break_distance,
        )

        atr_strength = self._calculate_atr_strength(
            current_swing=current_swing,
        )

        pivot_strength = self._calculate_pivot_strength(
            current_swing=current_swing,
        )

        confirmation_strength = (
            self._calculate_confirmation_strength(
                current_swing=current_swing,
            )
        )

        distance_strength = (
            self._calculate_distance_strength(
                current_swing=current_swing,
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

        return BOSMeasurement(
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

        #
        # Conservative linear normalization.
        #
        # Later this can be replaced with ATR-normalized
        # or percentile-normalized distance.
        #
        return min(
            break_distance / self.config.break_distance_normalizer,
            1.0,
        )

    def _calculate_atr_strength(
        self,
        current_swing: SwingPoint,
    ) -> float:
        """
        Normalize ATR multiple.
        """

        return min(
            max(
                current_swing.atr_multiple / self.config.atr_multiple_normalizer,
                0.0,
            ),
            1.0,
        )

    def _calculate_pivot_strength(
        self,
        current_swing: SwingPoint,
    ) -> float:
        """
        Normalize pivot dominance.
        """

        return min(
            max(
                current_swing.pivot_dominance,
                0.0,
            ),
            1.0,
        )

    def _calculate_confirmation_strength(
        self,
        current_swing: SwingPoint,
    ) -> float:
        """
        Normalize swing confirmation strength.
        """

        return min(
            max(
                current_swing.confirmation_strength,
                0.0,
            ),
            1.0,
        )

    def _calculate_distance_strength(
        self,
        current_swing: SwingPoint,
    ) -> float:
        """
        Normalize the distance from the previous confirmed swing.

        Larger distances generally indicate a more meaningful
        structural break.
        """

        if current_swing.distance_from_previous <= 0.0:
            return 0.0

        return min(
            current_swing.distance_from_previous / self.config.swing_distance_normalizer,
            1.0,
        )

    ####################################################################
    # Future OHLCV Measurements
    #
    # These methods are intentionally left for Version 2.
    # The MarketStructureEngine now preserves bar_history,
    # allowing these measurements to be implemented without
    # changing the detector.
    #
    # Planned Features:
    #   ✓ Body Ratio
    #   ✓ Upper Wick Ratio
    #   ✓ Lower Wick Ratio
    #   ✓ Relative Volume
    #   ✓ ATR Expansion
    #   ✓ Break Percentile
    #   ✓ Range Percentile
    #   ✓ Break Efficiency
    ####################################################################