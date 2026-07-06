from __future__ import annotations

from typing import Any

from core.trading_pipeline.models import MarketBar
from core.intelligence.contracts.entropy_state import EntropyState
from core.intelligence.contracts.explanation import Explanation
from core.intelligence.contracts.enums import Timeframe


class EntropyController:
    """
    Sprint 2 Final Layer — Entropy Controller

    Purpose:
        Control system-level trade frequency using information entropy logic.

    Key Idea:
        Even good setups are invalid if market entropy is too high.
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
    ) -> EntropyState:

        entropy_score = self._calculate_entropy(
            regime,
            scarcity,
            bias,
            structure,
            setup,
            entry,
        )

        allowed = self._is_allowed(entropy_score)

        explanations = self._build_explanations(entropy_score, allowed)

        return EntropyState(
            timestamp=bias.timestamp,
            symbol=self.symbol,
            timeframe=Timeframe.H1,
            engine_version="EntropyController-1.0.0",
            entropy_score=entropy_score,
            allowed=allowed,
            confidence=1.0 - entropy_score,
            explanations=tuple(explanations),
            metadata={
                "entropy_score": entropy_score,
            },
        )

    # --------------------------------------------------
    # ENTROPY CALCULATION (CORE LOGIC)
    # --------------------------------------------------
    def _calculate_entropy(
        self,
        regime: Any,
        scarcity: Any,
        bias: Any,
        structure: Any,
        setup: Any,
        entry: Any,
    ) -> float:

        score = 0.0

        # Regime clarity
        if hasattr(regime, "tradable") and regime.tradable:
            score += 0.2

        # Scarcity (important)
        if hasattr(scarcity, "allowed") and scarcity.allowed:
            score += 0.2

        # Bias strength
        if hasattr(bias, "confidence"):
            score += bias.confidence * 0.2

        # Structure quality
        if hasattr(structure, "confidence"):
            score += structure.confidence * 0.2

        # Setup quality
        if hasattr(setup, "confidence"):
            score += setup.confidence * 0.15

        # Entry quality
        if hasattr(entry, "confidence"):
            score += entry.confidence * 0.05

        return min(1.0, score)

    # --------------------------------------------------
    # FINAL DECISION GATE
    # --------------------------------------------------
    def _is_allowed(self, entropy_score: float) -> bool:

        # ❗ CORE RULE: only low entropy markets are tradable

        if entropy_score < 0.55:
            return False

        if entropy_score > 0.92:
            return False  # too perfect → usually fake / overextended

        return True

    # --------------------------------------------------
    # EXPLANATIONS
    # --------------------------------------------------
    def _build_explanations(
        self,
        entropy_score: float,
        allowed: bool,
    ) -> list[Explanation]:

        return [
            Explanation(
                source="ENTROPY_CONTROLLER",
                timeframe=Timeframe.H1,
                rule="ENTROPY_SCORE",
                category="SYSTEM",
                message=f"Entropy score: {entropy_score:.3f}",
                confidence=0.8,
                metadata={},
            ),
            Explanation(
                source="ENTROPY_CONTROLLER",
                timeframe=Timeframe.H1,
                rule="TRADE_PERMISSION",
                category="SYSTEM",
                message=f"Trade allowed: {allowed}",
                confidence=0.9,
                metadata={},
            ),
        ]
    