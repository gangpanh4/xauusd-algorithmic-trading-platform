from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional
import math


@dataclass
class OpportunityScore:
    symbol: str
    score: float
    confidence: float
    components: Dict[str, float]
    reason: str


class OpportunityRanker:
    """
    Sprint 5 — Edge Amplification Engine (FINAL VERSION)

    PURPOSE:
        Convert market context into true edge-separated opportunity ranking.

    KEY IDEA:
        NOT scoring.
        NOT weighting.
        BUT: regime-conditioned nonlinear edge separation.
    """

    # --------------------------------------------------
    # MAIN ENTRY
    # --------------------------------------------------
    def rank(self, context: Dict[str, Any], regime: Optional[str] = None) -> OpportunityScore:

        liq = self._score_liquidity(context)
        struct = self._score_structure(context)
        micro = self._score_microstructure(context)
        conf = self._score_confluence(context)
        entropy = self._score_entropy(context)

        # -----------------------------
        # HARD GATES (EDGE FILTERING)
        # -----------------------------
        if conf < 0.35:
            return self._zero(context, "LOW CONFLUENCE EDGE")

        if liq < 0.30:
            return self._zero(context, "LOW LIQUIDITY EDGE")

        # -----------------------------
        # REGIME WEIGHT MODEL
        # -----------------------------
        w = self._regime_weights(regime)

        # -----------------------------
        # INTERACTION-BASED EDGE MODEL
        # -----------------------------
        structure_micro = struct * micro
        liquidity_conf = liq * conf

        raw_edge = (
            w["micro"] * structure_micro +
            w["liquidity"] * liquidity_conf +
            w["structure"] * struct +
            w["entropy"] * (1.0 - entropy)
        )

        # -----------------------------
        # NONLINEAR SEPARATION (CORE)
        # -----------------------------
        print("=" * 60)
        print("OpportunityRanker")
        print(f"Liquidity      : {liq:.3f}")
        print(f"Structure      : {struct:.3f}")
        print(f"Microstructure : {micro:.3f}")
        print(f"Confluence     : {conf:.3f}")
        print(f"Entropy        : {entropy:.3f}")
        print(f"Raw Edge       : {raw_edge:.3f}")

        score = self._sigmoid_separation(raw_edge)

        # -----------------------------
        # EDGE AMPLIFICATION ZONE
        # -----------------------------
        if structure_micro > 0.75 and liquidity_conf > 0.75:
            score = min(1.0, score + 0.12)

        # -----------------------------
        # FINAL CLASSIFICATION
        # -----------------------------
        reason = self._classify(score)

        return OpportunityScore(
            symbol=context.get("symbol", "XAUUSD"),
            score=round(score, 4),
            confidence=score,
            components={
                "liquidity": liq,
                "structure": struct,
                "microstructure": micro,
                "confluence": conf,
                "entropy": entropy,
                "structure_micro": structure_micro,
                "liquidity_conf": liquidity_conf,
                "raw_edge": raw_edge,
            },
            reason=reason
        )

    # --------------------------------------------------
    # REGIME WEIGHTS (CORE UPGRADE)
    # --------------------------------------------------
    def _regime_weights(self, regime: Optional[str]) -> Dict[str, float]:

        if regime == "TRENDING":
            return {
                "micro": 0.45,
                "structure": 0.30,
                "liquidity": 0.15,
                "entropy": 0.10
            }

        if regime == "RANGING":
            return {
                "micro": 0.15,
                "structure": 0.15,
                "liquidity": 0.55,
                "entropy": 0.15
            }

        if regime == "VOLATILE":
            return {
                "micro": 0.20,
                "structure": 0.10,
                "liquidity": 0.25,
                "entropy": 0.45
            }

        # default balanced
        return {
            "micro": 0.25,
            "structure": 0.25,
            "liquidity": 0.25,
            "entropy": 0.25
        }

    # --------------------------------------------------
    # NONLINEAR SEPARATION ENGINE
    # --------------------------------------------------
    def _sigmoid_separation(self, x: float) -> float:
        return 1 / (1 + math.exp(-10 * (x - 0.5)))

    # --------------------------------------------------
    # SCORING HELPERS
    # --------------------------------------------------
    def _score_liquidity(self, c):
        return getattr(c.get("liquidity"), "liquidity_score", 0.5)

    def _score_structure(self, c):
        return getattr(c.get("structure"), "confidence", 0.5)

    def _score_microstructure(self, c):
        return getattr(c.get("microstructure"), "impulse_probability", 0.5)

    def _score_confluence(self, c):
        return getattr(c.get("confluence"), "score", 0.5)

    def _score_entropy(self, c):
        return getattr(c.get("entropy"), "entropy", 0.5)

    # --------------------------------------------------
    # ZERO EDGE RETURN
    # --------------------------------------------------
    def _zero(self, context: Dict[str, Any], reason: str) -> OpportunityScore:
        return OpportunityScore(
            symbol=context.get("symbol", "XAUUSD"),
            score=0.0,
            confidence=0.0,
            components={},
            reason=reason
        )

    # --------------------------------------------------
    # CLASSIFICATION
    # --------------------------------------------------
    def _classify(self, score: float) -> str:

        if score > 0.80:
            return "HIGH EDGE OPPORTUNITY"
        if score > 0.65:
            return "VALID EDGE OPPORTUNITY"
        if score > 0.45:
            return "LOW EDGE OPPORTUNITY"
        return "NO EDGE"