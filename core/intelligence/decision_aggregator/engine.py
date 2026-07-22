from __future__ import annotations

from core.intelligence.contracts.trading_signal import TradingSignal
from core.intelligence.contracts.market_bias import MarketBias
from core.intelligence.contracts.market_structure import MarketStructure
from core.intelligence.contracts.trade_setup import TradeSetup
from core.intelligence.contracts.entry_trigger import EntryTrigger
from core.intelligence.contracts.enums import (
    BiasDirection,
    TradingDecision,
    SetupQuality,
    EntryState,
)


class DecisionAggregator:
    """
    DecisionAggregator v2 (Sprint 2 Final Brain)

    Purpose:
        Convert multi-timeframe intelligence into a single trading decision.

    Key Upgrade:
        - Hard rejection rules
        - Hierarchical weighting
        - Institutional alignment scoring
    """

    def __init__(self, symbol: str):
        self.symbol = symbol

    # --------------------------------------------------
    # MAIN ENTRY
    # --------------------------------------------------
    def process(
        self,
        bias: MarketBias,
        structure: MarketStructure,
        setup: TradeSetup,
        entry: EntryTrigger,
    ) -> TradingSignal:

        # -----------------------------
        # HARD BLOCK RULES
        # -----------------------------
        if not self._passes_hard_filters(structure, setup, entry):
            return self._neutral_signal(bias, reason="Hard filter rejection")

        # -----------------------------
        # ALIGNMENT SCORE
        # -----------------------------
        score = self._calculate_alignment(
            bias,
            structure,
            setup,
            entry,
        )

        # -----------------------------
        # FINAL DECISION
        # -----------------------------
        decision = self._make_decision(score, bias)

        return TradingSignal(
            symbol=self.symbol,
            timestamp=bias.timestamp,
            decision=decision,
            confidence=score,
            bias=bias.bias,
            metadata={
                "alignment_score": score,
                "h4_bias": bias.bias.name,
                "h1_structure": structure.structure_state.name,
                "m15_quality": setup.setup_quality.name,
                "m5_entry": entry.state.name,
            },
        )

    # --------------------------------------------------
    # HARD FILTERS (CRITICAL GATE)
    # --------------------------------------------------
    def _passes_hard_filters(
        self,
        structure: MarketStructure,
        setup: TradeSetup,
        entry: EntryTrigger,
    ) -> bool:

        # M5 MUST allow entry
        if entry.state != EntryState.ENTRY_ALLOWED:
            return False

        # M15 must NOT be weak
        if setup.setup_quality == SetupQuality.LOW:
            return False

        # H1 must confirm structure (BOS required)
        if "BOS" not in structure.structure_state.name:
            return False

        return True

    # --------------------------------------------------
    # ALIGNMENT SCORING (WEIGHTED MODEL)
    # --------------------------------------------------
    def _calculate_alignment(
        self,
        bias: MarketBias,
        structure: MarketStructure,
        setup: TradeSetup,
        entry: EntryTrigger,
    ) -> float:

        score = 0.0

        # H4 bias (MOST IMPORTANT)
        if bias.bias in [BiasDirection.BUY, BiasDirection.SELL]:
            score += 0.30

        # H1 structure confirmation
        if "BOS" in structure.structure_state.name:
            score += 0.25

        # M15 setup quality
        if setup.setup_quality == SetupQuality.INSTITUTIONAL:
            score += 0.25
        elif setup.setup_quality == SetupQuality.HIGH:
            score += 0.15

        # M5 entry timing
        if entry.state == EntryState.ENTRY_ALLOWED:
            score += 0.20

        return score

    # --------------------------------------------------
    # DECISION LOGIC
    # --------------------------------------------------
    def _make_decision(
        self,
        score: float,
        bias: MarketBias,
    ) -> TradingDecision:

        if score >= 0.80:
            return (
                TradingDecision.BUY
                if bias.bias == BiasDirection.BUY
                else TradingDecision.SELL
            )

        return TradingDecision.NEUTRAL

    # --------------------------------------------------
    # FALLBACK
    # --------------------------------------------------
    def _neutral_signal(self, bias: MarketBias, reason: str) -> TradingSignal:

        return TradingSignal(
            symbol=self.symbol,
            timestamp=bias.timestamp,
            decision=TradingDecision.NEUTRAL,
            confidence=0.0,
            bias=bias.bias,
            metadata={
                "reason": reason,
            },
        )