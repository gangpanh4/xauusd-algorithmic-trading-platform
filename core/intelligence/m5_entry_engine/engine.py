from __future__ import annotations

from typing import List

from core.trading_pipeline.models import MarketBar
from core.intelligence.contracts.entry_trigger import EntryTrigger
from core.intelligence.contracts.explanation import Explanation
from core.intelligence.contracts.enums import (
    EntryState,
    TimingQuality,
    Timeframe,
)


class M5EntryEngine:
    """
    M5 Entry Engine v2 (Sprint 2 Strict Execution Filter)

    Purpose:
        Act as final execution gate before DecisionAggregator.

    Key Upgrade:
        - Strict multi-condition entry gating
        - Strong rejection logic
        - No weak/uncertain entries allowed
    """

    def __init__(self, symbol: str):
        self.symbol = symbol

    # --------------------------------------------------
    # MAIN ENTRY
    # --------------------------------------------------
    def process(
        self,
        bars: List[MarketBar],
        m15_confidence: float,
    ) -> EntryTrigger:

        if not bars or len(bars) < 10:
            return self._reject(bars, m15_confidence, "Insufficient data")

        micro = self._detect_micro_structure(bars)
        timing = self._evaluate_timing(bars)

        allowed = self._evaluate_entry_gate(
            micro=micro,
            timing=timing,
            m15_confidence=m15_confidence,
        )

        state = EntryState.ENTRY_ALLOWED if allowed else EntryState.ENTRY_DENIED

        explanations = self._build_explanations(micro, timing, allowed)
        confidence = self._calculate_confidence(explanations)

        return EntryTrigger(
            timestamp=bars[-1].timestamp,
            symbol=self.symbol,
            timeframe=Timeframe.M5,
            engine_version="M5EntryEngine-2.0.0",
            state=state,
            confidence=confidence,
            micro_structure=micro,
            timing_quality=timing,
            evidence=tuple(explanations),
            explanations=tuple(explanations),
            metadata={
                "m15_confidence": m15_confidence,
            },
        )

    # --------------------------------------------------
    # MICRO STRUCTURE
    # --------------------------------------------------
    def _detect_micro_structure(self, bars: List[MarketBar]) -> str:

        last = bars[-1]
        prev = bars[-2]

        body = abs(last.close - last.open)
        range_size = last.high - last.low

        if last.close > prev.high and body > range_size * 0.5:
            return "BREAKOUT"

        if last.close < prev.low and body > range_size * 0.5:
            return "BREAKDOWN"

        if body < range_size * 0.3:
            return "COMPRESSION"

        return "RANGE"

    # --------------------------------------------------
    # TIMING QUALITY
    # --------------------------------------------------
    def _evaluate_timing(self, bars: List[MarketBar]) -> TimingQuality:

        volatility = sum(b.high - b.low for b in bars[-5:]) / 5

        if volatility < 0.6:
            return TimingQuality.EARLY

        if volatility > 1.8:
            return TimingQuality.LATE

        return TimingQuality.OPTIMAL

    # --------------------------------------------------
    # ENTRY GATE LOGIC (CRITICAL UPGRADE)
    # --------------------------------------------------
    def _evaluate_entry_gate(
        self,
        micro: str,
        timing: TimingQuality,
        m15_confidence: float,
    ) -> bool:

        # HARD FILTER 1: M15 must be strong
        if m15_confidence < 0.65:
            return False

        # HARD FILTER 2: Timing must be optimal
        if timing != TimingQuality.OPTIMAL:
            return False

        # HARD FILTER 3: Must have directional micro confirmation
        if micro not in ["BREAKOUT", "BREAKDOWN"]:
            return False

        return True

    # --------------------------------------------------
    # EXPLANATIONS
    # --------------------------------------------------
    def _build_explanations(
        self,
        micro: str,
        timing: TimingQuality,
        allowed: bool,
    ) -> List[Explanation]:

        return [
            Explanation(
                source="M5_ENTRY_ENGINE_V2",
                timeframe=Timeframe.M5,
                rule="MICRO_STRUCTURE",
                category="ENTRY",
                message=f"Micro structure: {micro}",
                confidence=0.7,
                metadata={},
            ),
            Explanation(
                source="M5_ENTRY_ENGINE_V2",
                timeframe=Timeframe.M5,
                rule="TIMING",
                category="ENTRY",
                message=f"Timing: {timing}",
                confidence=0.7,
                metadata={},
            ),
            Explanation(
                source="M5_ENTRY_ENGINE_V2",
                timeframe=Timeframe.M5,
                rule="ENTRY_GATE",
                category="ENTRY",
                message=f"Entry allowed: {allowed}",
                confidence=0.8 if allowed else 0.2,
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
    # FALLBACK
    # --------------------------------------------------
    def _reject(
        self,
        bars: List[MarketBar],
        m15_confidence: float,
        reason: str,
    ) -> EntryTrigger:

        return EntryTrigger(
            timestamp=bars[-1].timestamp if bars else None,
            symbol=self.symbol,
            timeframe=Timeframe.M5,
            engine_version="M5EntryEngine-2.0.0",
            state=EntryState.ENTRY_DENIED,
            confidence=0.0,
            micro_structure="INVALID",
            timing_quality=TimingQuality.INVALID,
            evidence=(),
            explanations=(),
            metadata={
                "reason": reason,
                "m15_confidence": m15_confidence,
            },
        )