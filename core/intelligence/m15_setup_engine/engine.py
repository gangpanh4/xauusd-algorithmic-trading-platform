from __future__ import annotations

from typing import List

from core.trading_pipeline.models import MarketBar
from core.intelligence.contracts.trade_setup import TradeSetup
from core.intelligence.contracts.explanation import Explanation
from core.intelligence.contracts.enums import (
    BiasDirection,
    Timeframe,
    SetupQuality,
)


class M15SetupEngine:
    """
    M15 Setup Engine v2 (Institutional Filter Model)

    Key Upgrade:
        - Hard filters (disqualification rules)
        - Weighted confluence scoring
        - Non-linear setup evaluation
    """

    def __init__(self, symbol: str):
        self.symbol = symbol

    # --------------------------------------------------
    # MAIN ENTRY
    # --------------------------------------------------
    def process(
        self,
        bars: List[MarketBar],
        h4_bias: BiasDirection,
        h1_confirmed: bool,
    ) -> TradeSetup:

        if len(bars) < 20:
            return self._invalid(bars, h4_bias)

        # ----------------------------
        # HARD FILTERS (CRITICAL)
        # ----------------------------
        if not self._has_liquidity_sweep(bars):
            return self._invalid(bars, h4_bias, "No liquidity sweep")

        if not h1_confirmed:
            return self._invalid(bars, h4_bias, "H1 structure not confirmed")

        if not self._in_bias_zone(bars, h4_bias):
            return self._invalid(bars, h4_bias, "Not in premium/discount zone")

        # ----------------------------
        # SOFT CONFLUENCE SCORING
        # ----------------------------
        liquidity_score = self._liquidity_score(bars)
        fvg_score = self._fvg_score(bars)
        ob_score = self._order_block_score(bars)
        session_score = self._session_score(bars)

        # Weighted model (IMPORTANT FIX)
        confluence = (
            liquidity_score * 0.35 +
            fvg_score * 0.25 +
            ob_score * 0.25 +
            session_score * 0.15
        )

        quality = self._map_quality(confluence)

        explanations = self._build_explanations(
            liquidity_score,
            fvg_score,
            ob_score,
            session_score,
            confluence,
        )

        return TradeSetup(
            timestamp=bars[-1].timestamp,
            symbol=self.symbol,
            timeframe=Timeframe.M15,
            engine_version="M15SetupEngine-2.0.0",
            expected_direction=h4_bias,
            setup_quality=quality,
            confidence=confluence,
            components=(),
            evidence=tuple(explanations),
            explanations=tuple(explanations),
            metadata={
                "liquidity_score": liquidity_score,
                "fvg_score": fvg_score,
                "order_block_score": ob_score,
                "session_score": session_score,
            },
        )

    # --------------------------------------------------
    # HARD FILTERS
    # --------------------------------------------------
    def _has_liquidity_sweep(self, bars: List[MarketBar]) -> bool:
        recent = bars[-10:]

        highs = [b.high for b in recent]
        lows = [b.low for b in recent]

        return (
            highs[-1] > max(highs[:-2]) or
            lows[-1] < min(lows[:-2])
        )

    def _in_bias_zone(self, bars: List[MarketBar], bias: BiasDirection) -> bool:
        recent = bars[-20:]
        high = max(b.high for b in recent)
        low = min(b.low for b in recent)

        mid = (high + low) / 2
        price = recent[-1].close

        if bias == BiasDirection.BUY:
            return price < mid

        if bias == BiasDirection.SELL:
            return price > mid

        return False

    # --------------------------------------------------
    # SOFT SCORING
    # --------------------------------------------------
    def _liquidity_score(self, bars): return 1.0

    def _fvg_score(self, bars):
        recent = bars[-3:]
        if len(recent) < 3:
            return 0.0
        return 1.0 if recent[2].low > recent[0].high else 0.4

    def _order_block_score(self, bars):
        body = abs(bars[-1].close - bars[-1].open)
        return min(1.0, body / 5)

    def _session_score(self, bars):
        return 0.7  # placeholder (future upgrade)

    # --------------------------------------------------
    # QUALITY MAPPING
    # --------------------------------------------------
    def _map_quality(self, score: float) -> SetupQuality:

        if score >= 0.85:
            return SetupQuality.INSTITUTIONAL
        if score >= 0.70:
            return SetupQuality.HIGH
        if score >= 0.50:
            return SetupQuality.MODERATE
        return SetupQuality.LOW

    # --------------------------------------------------
    # EXPLANATIONS
    # --------------------------------------------------
    def _build_explanations(
        self,
        liquidity,
        fvg,
        ob,
        session,
        confluence,
    ) -> List[Explanation]:

        return [
            Explanation(
                source="M15_SETUP_V2",
                timeframe=Timeframe.M15,
                rule="CONFLUENCE",
                category="SETUP",
                message=f"Weighted confluence: {confluence:.2f}",
                confidence=confluence,
                metadata={},
            )
        ]

    # --------------------------------------------------
    # FALLBACK
    # --------------------------------------------------
    def _invalid(self, bars, bias, reason="Invalid setup"):

        return TradeSetup(
            timestamp=bars[-1].timestamp if bars else None,
            symbol=self.symbol,
            timeframe=Timeframe.M15,
            engine_version="M15SetupEngine-2.0.0",
            expected_direction=bias,
            setup_quality=SetupQuality.LOW,
            confidence=0.0,
            components=(),
            evidence=(),
            explanations=(),
            metadata={"reason": reason},
        )