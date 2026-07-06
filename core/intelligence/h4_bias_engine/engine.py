from __future__ import annotations

from typing import List

from core.trading_pipeline.models import MarketBar
from core.intelligence.contracts.market_bias import MarketBias
from core.intelligence.contracts.explanation import Explanation
from core.intelligence.contracts.enums import (
    BiasDirection,
    TrendState,
    MarketPhase,
    BiasStrength,
    Timeframe,
)


class H4BiasEngine:
    """
    H4 Bias Engine (Sprint 2)

    Purpose:
        Identify macro market direction and behavior using H4 structure.

    Output:
        MarketBias (immutable intelligence artifact)
    """

    def __init__(self, symbol: str):
        self.symbol = symbol

    # --------------------------------------------------
    # MAIN ENTRY
    # --------------------------------------------------
    def process(self, bars: List[MarketBar]) -> MarketBias:
        """
        Generate H4 MarketBias from historical bars.
        """

        if not bars or len(bars) < 20:
            return self._neutral_bias(bars)

        trend = self._detect_trend(bars)
        phase = self._detect_phase(bars)
        bias = self._derive_bias(trend)

        explanations = self._build_explanations(bars, trend, phase)
        confidence = self._calculate_confidence(explanations)

        return MarketBias(
            timestamp=bars[-1].timestamp,
            symbol=self.symbol,
            timeframe=Timeframe.H4,
            engine_version="H4BiasEngine-1.0.0",
            trend=trend,
            market_phase=phase,
            bias=bias,
            strength=self._map_strength(confidence),
            confidence=confidence,
            explanations=tuple(explanations),
            metadata={
                "bars_analyzed": len(bars),
            },
        )

    # --------------------------------------------------
    # TREND DETECTION (refined but still simple Sprint 2 v1)
    # --------------------------------------------------
    def _detect_trend(self, bars: List[MarketBar]) -> TrendState:
        recent = bars[-10:]

        up_moves = 0
        down_moves = 0

        for i in range(1, len(recent)):
            if recent[i].close > recent[i - 1].close:
                up_moves += 1
            elif recent[i].close < recent[i - 1].close:
                down_moves += 1

        if up_moves > down_moves:
            return TrendState.BULLISH

        if down_moves > up_moves:
            return TrendState.BEARISH

        return TrendState.NEUTRAL

    # --------------------------------------------------
    # PHASE DETECTION
    # --------------------------------------------------
    def _detect_phase(self, bars: List[MarketBar]) -> MarketPhase:
        recent = bars[-10:]

        volatility = max(b.high for b in recent) - min(b.low for b in recent)
        avg_range = sum(b.high - b.low for b in recent) / len(recent)

        if volatility < avg_range * 0.6:
            return MarketPhase.RANGING

        if volatility > avg_range * 1.5:
            return MarketPhase.IMPULSIVE

        return MarketPhase.CONSOLIDATING

    # --------------------------------------------------
    # BIAS DERIVATION
    # --------------------------------------------------
    def _derive_bias(self, trend: TrendState) -> BiasDirection:
        if trend == TrendState.BULLISH:
            return BiasDirection.BUY

        if trend == TrendState.BEARISH:
            return BiasDirection.SELL

        return BiasDirection.NEUTRAL

    # --------------------------------------------------
    # EXPLANATIONS (clean Sprint 2 version)
    # --------------------------------------------------
    def _build_explanations(
        self,
        bars: List[MarketBar],
        trend: TrendState,
        phase: MarketPhase,
    ) -> List[Explanation]:

        return [
            Explanation(
                source="H4_BIAS_ENGINE",
                timeframe=Timeframe.H4,
                rule="TREND_DETECTION",
                category="TREND",
                message=f"H4 trend detected as {trend}",
                confidence=0.7,
                metadata={},
            ),
            Explanation(
                source="H4_BIAS_ENGINE",
                timeframe=Timeframe.H4,
                rule="PHASE_DETECTION",
                category="MARKET_PHASE",
                message=f"H4 market phase identified as {phase}",
                confidence=0.7,
                metadata={},
            ),
        ]

    # --------------------------------------------------
    # CONFIDENCE
    # --------------------------------------------------
    def _calculate_confidence(self, explanations: List[Explanation]) -> float:
        if not explanations:
            return 0.0

        return sum(e.confidence for e in explanations) / len(explanations)

    # --------------------------------------------------
    # STRENGTH MAPPING
    # --------------------------------------------------
    def _map_strength(self, confidence: float) -> BiasStrength:
        if confidence >= 0.80:
            return BiasStrength.STRONG

        if confidence >= 0.50:
            return BiasStrength.MODERATE

        return BiasStrength.WEAK

    # --------------------------------------------------
    # FALLBACK
    # --------------------------------------------------
    def _neutral_bias(self, bars: List[MarketBar]) -> MarketBias:
        last_ts = bars[-1].timestamp if bars else None

        return MarketBias(
            timestamp=last_ts,
            symbol=self.symbol,
            timeframe=Timeframe.H4,
            engine_version="H4BiasEngine-1.0.0",
            trend=TrendState.NEUTRAL,
            market_phase=MarketPhase.RANGING,
            bias=BiasDirection.NEUTRAL,
            strength=BiasStrength.WEAK,
            confidence=0.0,
            explanations=tuple(),
            metadata={
                "reason": "insufficient_data",
            },
        )