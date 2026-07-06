from __future__ import annotations

from typing import Any

from core.intelligence.contracts.confluence_state import ConfluenceState
from core.intelligence.contracts.explanation import Explanation
from core.intelligence.contracts.enums import Timeframe


class ConfluenceEngine:
    """
    Sprint 3 — Liquidity + Structure Confluence Engine

    PURPOSE:
        Merge ALL directional signals into ONE unified market interpretation.

    KEY IDEA:
        Edge exists only when liquidity + structure + bias align.
    """

    def __init__(self, symbol: str):
        self.symbol = symbol

    # --------------------------------------------------
    # MAIN ENTRY
    # --------------------------------------------------
    def process(
        self,
        liquidity_bias: Any,
        h4_bias: Any,
        structure: Any,
    ) -> ConfluenceState:

        score = self._calculate_confluence(
            liquidity_bias,
            h4_bias,
            structure,
        )

        direction = self._final_direction(score)

        allowed = self._is_allowed(score)

        explanations = self._build_explanations(score, direction, allowed)

        return ConfluenceState(
            timestamp=structure.timestamp,
            symbol=self.symbol,
            timeframe=Timeframe.H1,
            engine_version="ConfluenceEngine-1.0.0",
            score=score,
            direction=direction,
            allowed=allowed,
            confidence=score,
            explanations=tuple(explanations),
            metadata={
                "mode": "liquidity_structure_bias_fusion",
            },
        )

    # --------------------------------------------------
    # CORE FUSION LOGIC
    # --------------------------------------------------
    def _calculate_confluence(self, liq, bias, structure) -> float:
        # --------------------------
        # HARD ALIGNMENT CHECKS
        # --------------------------
        alignment_count = 0
        total_checks = 3

        # 1. Liquidity alignment
        if liq.bias == "BULLISH":
            liq_score = 1
        elif liq.bias == "BEARISH":
            liq_score = -1
        else:
            liq_score = 0

        # 2. H4 alignment
        if hasattr(bias, "trend"):
            if bias.trend == "BULLISH":
                h4_score = 1
            elif bias.trend == "BEARISH":
                h4_score = -1
            else:
                h4_score = 0
        else:
            h4_score = 0

        # 3. Structure strength
        structure_score = getattr(structure, "confidence", 0)

        # --------------------------
        # ALIGNMENT RULES
        # --------------------------
        if liq_score != 0:
            alignment_count += 1
        if h4_score != 0:
            alignment_count += 1
        if structure_score > 0.6:
            alignment_count += 1

        # --------------------------
        # FINAL SCORE (STRICT)
        # --------------------------
        score = alignment_count / total_checks

        # penalize disagreement
        if liq_score != 0 and h4_score != 0:
            if liq_score != h4_score:
                score -= 0.5

        return max(0.0, min(1.0, score))

    # --------------------------------------------------
    # FINAL DIRECTION
    # --------------------------------------------------
    def _final_direction(self, score: float) -> str:

        if score > 0.4:
            return "BULLISH"

        if score < -0.4:
            return "BEARISH"

        return "NEUTRAL"

    # --------------------------------------------------
    # TRADE GATE
    # --------------------------------------------------
    def _is_allowed(self, score: float) -> bool:

        # ❗ ONLY HIGH CONFLUENCE ZONES TRADE
        return abs(score) > 0.55

    # --------------------------------------------------
    # EXPLANATIONS
    # --------------------------------------------------
    def _build_explanations(self, score, direction, allowed):

        return [
            Explanation(
                source="CONFLUENCE_ENGINE",
                timeframe=Timeframe.H1,
                rule="FUSION_SCORE",
                category="ALPHA",
                message=f"Confluence score: {score:.3f}",
                confidence=0.9,
                metadata={},
            ),
            Explanation(
                source="CONFLUENCE_ENGINE",
                timeframe=Timeframe.H1,
                rule="DIRECTION",
                category="ALPHA",
                message=f"Final direction: {direction}",
                confidence=0.9,
                metadata={},
            ),
            Explanation(
                source="CONFLUENCE_ENGINE",
                timeframe=Timeframe.H1,
                rule="TRADE_PERMISSION",
                category="ALPHA",
                message=f"Allowed: {allowed}",
                confidence=0.95,
                metadata={},
            ),
        ]