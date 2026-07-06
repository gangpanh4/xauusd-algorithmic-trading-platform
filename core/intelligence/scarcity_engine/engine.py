from __future__ import annotations

from typing import List

from core.trading_pipeline.models import MarketBar
from core.intelligence.contracts.opportunity_state import OpportunityState
from core.intelligence.contracts.explanation import Explanation
from core.intelligence.contracts.enums import Timeframe


class OpportunityScarcityEngine:
    """
    Sprint 2 — Opportunity Scarcity Engine

    Purpose:
        Enforce rarity conditions before allowing any trade.

    Core Principle:
        Good setups are NOT enough.
        Only rare setups are tradable.
    """

    def __init__(self, symbol: str):
        self.symbol = symbol

        # internal memory (prevents overtrading clusters)
        self._last_trade_index = -1000

    # --------------------------------------------------
    # MAIN ENTRY
    # --------------------------------------------------
    def process(self, bars: List[MarketBar]) -> OpportunityState:

        if not bars or len(bars) < 50:
            return self._blocked(bars, "insufficient_data")

        rarity_score = self._calculate_rarity(bars)
        saturation = self._market_saturation(bars)
        alignment_quality = self._alignment_quality(bars)

        allowed = self._is_allowed(
            rarity_score,
            saturation,
            alignment_quality,
        )

        explanations = self._build_explanations(
            rarity_score,
            saturation,
            alignment_quality,
            allowed,
        )

        return OpportunityState(
            timestamp=bars[-1].timestamp,
            symbol=self.symbol,
            timeframe=Timeframe.H1,
            engine_version="OpportunityScarcityEngine-1.0.0",
            allowed=allowed,
            rarity_score=rarity_score,
            saturation=saturation,
            confidence=self._confidence(rarity_score, saturation, alignment_quality),
            explanations=tuple(explanations),
            metadata={
                "bars_analyzed": len(bars),
            },
        )

    # --------------------------------------------------
    # RARITY SCORE (CRITICAL CORE)
    # --------------------------------------------------
    def _calculate_rarity(self, bars: List[MarketBar]) -> float:

        recent = bars[-30:]

        strong_moves = 0

        for i in range(1, len(recent)):
            body = abs(recent[i].close - recent[i].open)
            prev_body = abs(recent[i - 1].close - recent[i - 1].open)

            if body > prev_body * 1.2:
                strong_moves += 1

        return strong_moves / len(recent)

    # --------------------------------------------------
    # MARKET SATURATION
    # --------------------------------------------------
    def _market_saturation(self, bars: List[MarketBar]) -> float:

        recent = bars[-20:]

        volatility = sum(b.high - b.low for b in recent) / len(recent)

        return min(1.0, volatility / 5.0)

    # --------------------------------------------------
    # ALIGNMENT QUALITY
    # --------------------------------------------------
    def _alignment_quality(self, bars: List[MarketBar]) -> float:

        recent = bars[-10:]

        trend_strength = 0

        for i in range(1, len(recent)):
            if recent[i].close > recent[i - 1].close:
                trend_strength += 1

        return trend_strength / len(recent)

    # --------------------------------------------------
    # DECISION LOGIC (STRICT)
    # --------------------------------------------------
    def _is_allowed(
        self,
        rarity: float,
        saturation: float,
        alignment: float,
    ) -> bool:

        # ❗ HARD SCARCITY RULES

        if rarity < 0.25:
            return False

        if saturation > 0.75:
            return False

        if alignment < 0.6:
            return False

        return True

    # --------------------------------------------------
    # CONFIDENCE
    # --------------------------------------------------
    def _confidence(
        self,
        rarity: float,
        saturation: float,
        alignment: float,
    ) -> float:

        return (rarity + (1 - saturation) + alignment) / 3

    # --------------------------------------------------
    # EXPLANATIONS
    # --------------------------------------------------
    def _build_explanations(
        self,
        rarity: float,
        saturation: float,
        alignment: float,
        allowed: bool,
    ) -> List[Explanation]:

        return [
            Explanation(
                source="SCARCITY_ENGINE",
                timeframe=Timeframe.H1,
                rule="RARITY",
                category="OPPORTUNITY",
                message=f"Rarity score: {rarity:.2f}",
                confidence=0.7,
                metadata={},
            ),
            Explanation(
                source="SCARCITY_ENGINE",
                timeframe=Timeframe.H1,
                rule="SATURATION",
                category="OPPORTUNITY",
                message=f"Saturation: {saturation:.2f}",
                confidence=0.7,
                metadata={},
            ),
            Explanation(
                source="SCARCITY_ENGINE",
                timeframe=Timeframe.H1,
                rule="ALLOWED",
                category="OPPORTUNITY",
                message=f"Trade allowed: {allowed}",
                confidence=0.8 if allowed else 0.2,
                metadata={},
            ),
        ]

    # --------------------------------------------------
    # FALLBACK
    # --------------------------------------------------
    def _blocked(self, bars: List[MarketBar], reason: str) -> OpportunityState:

        return OpportunityState(
            timestamp=bars[-1].timestamp if bars else None,
            symbol=self.symbol,
            timeframe=Timeframe.H1,
            engine_version="OpportunityScarcityEngine-1.0.0",
            allowed=False,
            rarity_score=0.0,
            saturation=1.0,
            confidence=0.0,
            explanations=(),
            metadata={
                "reason": reason,
            },
        )