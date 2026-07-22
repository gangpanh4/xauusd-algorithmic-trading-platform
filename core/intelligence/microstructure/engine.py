from __future__ import annotations

from typing import List

from core.trading_pipeline.models import MarketBar
from core.intelligence.contracts.microstructure_state import MicrostructureSignal
from core.intelligence.contracts.explanation import Explanation
from core.intelligence.contracts.enums import Timeframe


class MarketMicrostructureEngine:
    """
    Sprint 4 — Market Microstructure Engine v1

    PURPOSE:
        Convert raw price action into event-based market physics:
        sweep → impulse → displacement chain

    KEY IDEA:
        Edge is not in patterns.
        Edge is in event sequences.
    """

    def __init__(self, symbol: str):
        self.symbol = symbol

    # --------------------------------------------------
    # MAIN ENTRY
    # --------------------------------------------------
    def process(self, bars: List[MarketBar]) -> MicrostructureSignal:

        sweeps = self._detect_sweeps(bars)
        impulses = self._detect_impulses(bars)

        displacement_chain = self._detect_sweep_to_impulse_chain(
            sweeps,
            impulses
        )

        probability = self._impulse_probability(
            sweeps,
            impulses,
            displacement_chain
        )

        direction = self._direction_bias(impulses)

        explanations = self._build_explanations(
            sweeps,
            impulses,
            displacement_chain,
            probability,
            direction,
        )

        return MicrostructureSignal(
            timestamp=bars[-1].timestamp,
            symbol=self.symbol,
            timeframe=Timeframe.M5,
            engine_version="MicrostructureEngine-1.0.0",
            sweeps=sweeps,
            impulses=impulses,
            displacement_chain=displacement_chain,
            impulse_probability=probability,
            direction=direction,
            confidence=probability,
            explanations=tuple(explanations),
            metadata={
                "model": "sweep_impulse_chain",
            },
        )

    # --------------------------------------------------
    # SWEEP DETECTION
    # --------------------------------------------------
    def _detect_sweeps(self, bars: List[MarketBar]) -> int:

        recent = bars[-20:]
        count = 0

        for i in range(2, len(recent)):
            if recent[i].high > recent[i-1].high and recent[i].close < recent[i].high:
                count += 1
            if recent[i].low < recent[i-1].low and recent[i].close > recent[i].low:
                count += 1

        return count

    # --------------------------------------------------
    # IMPULSE DETECTION
    # --------------------------------------------------
    def _detect_impulses(self, bars: List[MarketBar]) -> int:

        recent = bars[-10:]
        count = 0

        for i in range(1, len(recent)):
            body = abs(recent[i].close - recent[i].open)
            rng = recent[i].high - recent[i].low

            if rng > 0 and body / rng > 0.7:
                count += 1

        return count

    # --------------------------------------------------
    # SWEEP → IMPULSE CHAIN (CORE EDGE LOGIC)
    # --------------------------------------------------
    def _detect_sweep_to_impulse_chain(self, sweeps: int, impulses: int) -> float:

        if sweeps == 0:
            return 0.0

        return min(1.0, impulses / sweeps)

    # --------------------------------------------------
    # IMPULSE PROBABILITY MODEL
    # --------------------------------------------------
    def _impulse_probability(
        self,
        sweeps: int,
        impulses: int,
        chain: float,
    ) -> float:

        return min(1.0, (chain * 0.6) + (impulses * 0.2))

    # --------------------------------------------------
    # DIRECTION MODEL
    # --------------------------------------------------
    def _direction_bias(self, impulses: int) -> str:

        if impulses >= 3:
            return "TRENDING"
        elif impulses > 0:
            return "TRANSITION"
        return "RANGING"

    # --------------------------------------------------
    # EXPLANATIONS
    # --------------------------------------------------
    def _build_explanations(
        self,
        sweeps,
        impulses,
        chain,
        prob,
        direction,
    ):

        return [
            Explanation(
                source="MICROSTRUCTURE_ENGINE",
                timeframe=Timeframe.M5,
                rule="SWEEP_IMPULSE_CHAIN",
                category="ALPHA",
                message=f"Chain strength: {chain:.3f}",
                confidence=0.9,
                metadata={},
            ),
            Explanation(
                source="MICROSTRUCTURE_ENGINE",
                timeframe=Timeframe.M5,
                rule="IMPULSE_PROBABILITY",
                category="ALPHA",
                message=f"Impulse probability: {prob:.3f}",
                confidence=0.9,
                metadata={},
            ),
        ]