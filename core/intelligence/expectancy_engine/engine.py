from __future__ import annotations

from typing import Any

from core.trading_pipeline.models import MarketBar
from core.intelligence.contracts.expectancy_state import ExpectancyState
from core.intelligence.contracts.explanation import Explanation
from core.intelligence.contracts.enums import Timeframe


class ExpectancyEngine:
    """
    Sprint 3 (Foundation Layer) — Expectancy Engine

    Purpose:
        Evaluate whether a trade has positive statistical edge.

    Key Insight:
        Filters are NOT enough.
        We need EV-based selection.
    """

    def __init__(self, symbol: str):
        self.symbol = symbol

    # --------------------------------------------------
    # MAIN ENTRY
    # --------------------------------------------------
    def process(
        self,
        regime: Any,
        scarcity: Any,
        bias: Any,
        structure: Any,
        setup: Any,
        entry: Any,
        entropy: Any,
    ) -> ExpectancyState:

        ev_score = self._calculate_expectancy(
            regime,
            scarcity,
            bias,
            structure,
            setup,
            entry,
            entropy,
        )

        allowed = self._is_allowed(ev_score)

        explanations = self._build_explanations(ev_score, allowed)

        return ExpectancyState(
            timestamp=bias.timestamp,
            symbol=self.symbol,
            timeframe=Timeframe.H1,
            engine_version="ExpectancyEngine-1.0.0",
            expectancy=ev_score,
            allowed=allowed,
            confidence=min(1.0, abs(ev_score)),
            explanations=tuple(explanations),
            metadata={
                "ev_score": ev_score,
            },
        )

    # --------------------------------------------------
    # EXPECTANCY MODEL (CORE LOGIC)
    # --------------------------------------------------
    def _calculate_expectancy(
        self,
        regime: Any,
        scarcity: Any,
        bias: Any,
        structure: Any,
        setup: Any,
        entry: Any,
        entropy: Any,
    ) -> float:

        score = 0.0

        # -----------------------------
        # REGIME QUALITY
        # -----------------------------
        if hasattr(regime, "tradable") and regime.tradable:
            score += 0.25

        # -----------------------------
        # SCARCITY (IMPORTANT EDGE FACTOR)
        # -----------------------------
        if hasattr(scarcity, "allowed") and scarcity.allowed:
            score += 0.20

        # -----------------------------
        # STRUCTURE ALIGNMENT
        # -----------------------------
        if hasattr(structure, "confidence"):
            score += structure.confidence * 0.15

        # -----------------------------
        # SETUP QUALITY
        # -----------------------------
        if hasattr(setup, "confidence"):
            score += setup.confidence * 0.20

        # -----------------------------
        # ENTRY QUALITY
        # -----------------------------
        if hasattr(entry, "confidence"):
            score += entry.confidence * 0.10

        # -----------------------------
        # ENTROPY PENALTY (VERY IMPORTANT)
        # -----------------------------
        if hasattr(entropy, "entropy_score"):
            score -= entropy.entropy_score * 0.20

        # -----------------------------
        # BIAS STRENGTH BONUS
        # -----------------------------
        if hasattr(bias, "confidence"):
            score += bias.confidence * 0.10

        return score

    # --------------------------------------------------
    # TRADE FILTER
    # --------------------------------------------------
    def _is_allowed(self, ev_score: float) -> bool:

        # ❗ ONLY TRADE IF EDGE EXISTS
        return ev_score > 0.35

    # --------------------------------------------------
    # EXPLANATIONS
    # --------------------------------------------------
    def _build_explanations(
        self,
        ev_score: float,
        allowed: bool,
    ) -> list[Explanation]:

        return [
            Explanation(
                source="EXPECTANCY_ENGINE",
                timeframe=Timeframe.H1,
                rule="EXPECTED_VALUE",
                category="EDGE",
                message=f"EV score: {ev_score:.3f}",
                confidence=0.9,
                metadata={},
            ),
            Explanation(
                source="EXPECTANCY_ENGINE",
                timeframe=Timeframe.H1,
                rule="TRADE_PERMISSION",
                category="EDGE",
                message=f"Trade allowed: {allowed}",
                confidence=0.9,
                metadata={},
            ),
        ]