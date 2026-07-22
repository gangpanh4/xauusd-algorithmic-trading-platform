"""
Liquidity Measurement Engine.

Computes continuous measurements for confirmed liquidity
sweeps. The detector is responsible only for detecting a
liquidity event. This engine evaluates the quality of that
event.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.market_structure.models import LiquidityEvent


@dataclass(slots=True, frozen=True)
class LiquidityMeasurement:
    """
    Continuous measurements describing the quality of a
    confirmed liquidity sweep.
    """

    sweep_distance: float

    atr_strength: float
    sweep_strength: float
    reaction_strength: float

    density: float
    reclaim_strength: float
    power_score: float
    structure_score: float

    quality: float


class LiquidityMeasurementEngine:
    """
    Computes continuous liquidity measurements.
    """

    def evaluate(
        self,
        event: LiquidityEvent,
    ) -> LiquidityMeasurement:

        sweep_strength = self._calculate_sweep_strength(
            event.sweep_distance,
        )

        atr_strength = self._calculate_atr_strength(
            event.atr_multiple,
        )

        reaction_strength = self._calculate_reaction_strength(
            event.reaction_strength,
        )

        # Assuming density and reclaim_strength exist on LiquidityEvent, 
        # using getattr as a safe fallback in case the model isn't updated yet.
        density = self._calculate_density(
            getattr(event, "density", 0.0),
        )

        reclaim_strength = self._calculate_reclaim_strength(
            getattr(event, "reclaim_strength", 0.0),
        )

        # Compute new component scores
        power_score = (
            0.34 * sweep_strength +
            0.33 * atr_strength +
            0.33 * reclaim_strength
        )

        structure_score = (
            0.50 * density +
            0.50 * reaction_strength
        )

        # Preserve original quality behavior
        quality = (
            0.40 * sweep_strength +
            0.30 * atr_strength +
            0.30 * reaction_strength
        )

        return LiquidityMeasurement(
            sweep_distance=event.sweep_distance,
            
            atr_strength=atr_strength,
            sweep_strength=sweep_strength,
            reaction_strength=reaction_strength,
            
            density=density,
            reclaim_strength=reclaim_strength,
            power_score=power_score,
            structure_score=structure_score,
            
            quality=quality,
        )

    def _calculate_sweep_strength(
        self,
        distance: float,
    ) -> float:

        if distance <= 0.0:
            return 0.0

        return min(
            distance / 20.0,
            1.0,
        )

    def _calculate_atr_strength(
        self,
        atr_multiple: float,
    ) -> float:

        return min(
            max(
                atr_multiple / 3.0,
                0.0,
            ),
            1.0,
        )

    def _calculate_reaction_strength(
        self,
        reaction_strength: float,
    ) -> float:

        return min(
            max(
                reaction_strength,
                0.0,
            ),
            1.0,
        )

    def _calculate_density(
        self,
        density: float,
    ) -> float:
        """
        Normalize liquidity density.
        """
        return min(
            max(
                density,
                0.0,
            ),
            1.0,
        )

    def _calculate_reclaim_strength(
        self,
        reclaim_strength: float,
    ) -> float:
        """
        Normalize liquidity reclaim strength.
        """
        return min(
            max(
                reclaim_strength,
                0.0,
            ),
            1.0,
        )