from __future__ import annotations

from typing import List

from core.trading_pipeline.models import MarketBar
from core.intelligence.contracts.directional_bias import DirectionalLiquidityBias
from core.intelligence.contracts.explanation import Explanation
from core.intelligence.contracts.enums import Timeframe


class DirectionalLiquidityEngine:
    """
    Sprint 3 — Directional Liquidity Bias Engine

    PURPOSE:
        Convert liquidity events into directional probability.

    CORE IDEA:
        Sweep + BOS sequence = directional intent.
    """

    def __init__(self, symbol: str):
        self.symbol = symbol

    # --------------------------------------------------
    # MAIN ENTRY
    # --------------------------------------------------
    def process(self, bars: List[MarketBar]) -> DirectionalLiquidityBias:

        sweeps = self._detect_sweeps(bars)
        bos = self._detect_bos(bars)

        direction_score = self._direction_score(sweeps, bos)

        bias = self._classify_bias(direction_score)

        explanations = self._build_explanations(sweeps, bos, direction_score, bias)

        return DirectionalLiquidityBias(
            timestamp=bars[-1].timestamp,
            symbol=self.symbol,
            timeframe=Timeframe.M15,
            engine_version="DirectionalLiquidityEngine-1.0.0",
            bias=bias,
            direction_score=direction_score,
            sweeps=sweeps,
            bos=bos,
            confidence=min(1.0, abs(direction_score)),
            explanations=tuple(explanations),
            metadata={
                "mode": "liquidity_directional_model",
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
    # BOS DETECTION
    # --------------------------------------------------
    def _detect_bos(self, bars: List[MarketBar]) -> int:
        recent = bars[-20:]
        bos = 0

        for i in range(2, len(recent)):
            if recent[i].close > recent[i-1].high:
                bos += 1
            if recent[i].close < recent[i-1].low:
                bos += 1

        return bos

    # --------------------------------------------------
    # DIRECTION SCORE (CORE EDGE LOGIC)
    # --------------------------------------------------
    def _direction_score(self, sweeps: int, bos: int) -> float:

        # 🔥 institutional weighting model
        return (bos * 0.7) - (sweeps * 0.5)

    # --------------------------------------------------
    # CLASSIFICATION
    # --------------------------------------------------
    def _classify_bias(self, score: float) -> str:

        if score > 1.0:
            return "BULLISH"

        if score < -1.0:
            return "BEARISH"

        return "NEUTRAL"

    # --------------------------------------------------
    # EXPLANATIONS
    # --------------------------------------------------
    def _build_explanations(self, sweeps, bos, score, bias):

        return [
            Explanation(
                source="DIRECTIONAL_LIQUIDITY",
                timeframe=Timeframe.M15,
                rule="SWEPT_BOS_MODEL",
                category="ALPHA",
                message=f"Directional score: {score:.2f}",
                confidence=0.85,
                metadata={},
            ),
            Explanation(
                source="DIRECTIONAL_LIQUIDITY",
                timeframe=Timeframe.M15,
                rule="BIAS",
                category="ALPHA",
                message=f"Bias: {bias}",
                confidence=0.9,
                metadata={},
            ),
        ]