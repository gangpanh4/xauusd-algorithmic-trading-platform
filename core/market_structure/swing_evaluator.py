"""Market-structure evidence evaluation.

Scores are based on measured event quality and completed-bar freshness. Raw
XAUUSD price distances are retained as diagnostics but are not treated as
universally positive evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from core.market_structure.models import (
    BOSEvent,
    CHOCHEvent,
    LiquiditySweepEvent,
    SwingPoint,
)


@dataclass(slots=True, frozen=True)
class StructureEvaluation:
    """Normalized market-structure evidence."""

    swing_score: float
    bos_score: float
    choch_score: float
    liquidity_score: float
    confidence: float
    bos_freshness: float = 0.0
    choch_freshness: float = 0.0
    liquidity_freshness: float = 0.0


class StructureEvaluator:
    """Evaluate current structure quality without direction assumptions."""

    def __init__(
        self,
        *,
        freshness_decay_bars: int = 8,
        swing_weight: float = 0.20,
        bos_weight: float = 0.35,
        choch_weight: float = 0.20,
        liquidity_weight: float = 0.25,
    ) -> None:
        if isinstance(freshness_decay_bars, bool) or not isinstance(
            freshness_decay_bars,
            int,
        ):
            raise TypeError("freshness_decay_bars must be an int")
        if freshness_decay_bars <= 0:
            raise ValueError("freshness_decay_bars must be > 0")

        weights = (
            swing_weight,
            bos_weight,
            choch_weight,
            liquidity_weight,
        )
        if any(
            isinstance(weight, bool)
            or not isinstance(weight, (int, float))
            or not math.isfinite(float(weight))
            or weight < 0.0
            for weight in weights
        ):
            raise ValueError("structure weights must be finite and >= 0")
        weight_total = float(sum(weights))
        if weight_total <= 0.0:
            raise ValueError("at least one structure weight must be > 0")

        self.freshness_decay_bars = freshness_decay_bars
        self.swing_weight = float(swing_weight) / weight_total
        self.bos_weight = float(bos_weight) / weight_total
        self.choch_weight = float(choch_weight) / weight_total
        self.liquidity_weight = float(liquidity_weight) / weight_total

    def evaluate(
        self,
        *,
        swing: SwingPoint | None,
        bos: BOSEvent | None,
        choch: CHOCHEvent | None,
        liquidity: LiquiditySweepEvent | None,
    ) -> StructureEvaluation:
        swing_score = self._swing_score(swing)
        bos_freshness = self._freshness(bos.age) if bos is not None else 0.0
        choch_freshness = (
            self._freshness(choch.age) if choch is not None else 0.0
        )
        liquidity_freshness = (
            self._freshness(liquidity.age)
            if liquidity is not None
            else 0.0
        )

        bos_score = (
            self._clamp(bos.quality) * bos_freshness
            if bos is not None
            else 0.0
        )
        choch_score = (
            self._clamp(choch.quality) * choch_freshness
            if choch is not None
            else 0.0
        )
        liquidity_score = (
            self._clamp(liquidity.quality) * liquidity_freshness
            if liquidity is not None
            else 0.0
        )

        confidence = self._clamp(
            swing_score * self.swing_weight
            + bos_score * self.bos_weight
            + choch_score * self.choch_weight
            + liquidity_score * self.liquidity_weight
        )

        return StructureEvaluation(
            swing_score=swing_score,
            bos_score=bos_score,
            choch_score=choch_score,
            liquidity_score=liquidity_score,
            confidence=confidence,
            bos_freshness=bos_freshness,
            choch_freshness=choch_freshness,
            liquidity_freshness=liquidity_freshness,
        )

    def _freshness(self, age: int) -> float:
        if age <= 0:
            return 1.0
        return math.exp(-age / self.freshness_decay_bars)

    @staticmethod
    def _swing_score(swing: SwingPoint | None) -> float:
        if swing is None:
            return 0.0
        return StructureEvaluator._clamp(
            0.35 * min(max(swing.atr_multiple / 3.0, 0.0), 1.0)
            + 0.30 * min(max(swing.pivot_dominance / 5.0, 0.0), 1.0)
            + 0.20
            * min(max(swing.distance_from_previous / 100.0, 0.0), 1.0)
            + 0.15 * min(max(swing.confirmation_strength, 0.0), 1.0)
        )

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(float(value), 1.0))
