from __future__ import annotations

from typing import List

from core.trading_pipeline.models import MarketBar
from core.intelligence.contracts.entry_state import EntryState
from core.intelligence.contracts.explanation import Explanation
from core.intelligence.contracts.enums import Timeframe


class M5EntryCompressionEngine:
    """
    Sprint 3 — M5 Entry Compression Engine

    PURPOSE:
        Filter execution timing to only allow high-momentum continuation entries.

    KEY IDEA:
        Setup is not enough.
        Entry timing is everything.
    """

    def __init__(self, symbol: str):
        self.symbol = symbol

    # --------------------------------------------------
    # MAIN ENTRY
    # --------------------------------------------------
    def process(
        self,
        bars: List[MarketBar],
        confluence_direction: str,
        liquidity_bias: str,
    ) -> EntryState:

        momentum = self._detect_momentum(bars)
        pullback_quality = self._detect_pullback(bars)
        entry_zone_quality = self._detect_entry_zone(bars)

        score = self._entry_score(momentum, pullback_quality, entry_zone_quality)

        allowed = self._is_allowed(score, confluence_direction, liquidity_bias)

        explanations = self._build_explanations(momentum, score, allowed)

        return EntryState(
            timestamp=bars[-1].timestamp,
            symbol=self.symbol,
            timeframe=Timeframe.M5,
            engine_version="M5EntryCompressionEngine-1.0.0",
            momentum=momentum,
            pullback_quality=pullback_quality,
            entry_zone_quality=entry_zone_quality,
            score=score,
            allowed=allowed,
            confidence=min(1.0, score),
            explanations=tuple(explanations),
            metadata={
                "mode": "execution_compression",
            },
        )

    # --------------------------------------------------
    # MOMENTUM DETECTION
    # --------------------------------------------------
    def _detect_momentum(self, bars: List[MarketBar]) -> int:

        recent = bars[-5:]
        count = 0

        for i in range(1, len(recent)):
            if abs(recent[i].close - recent[i].open) > (recent[i].high - recent[i].low) * 0.6:
                count += 1

        return count

    # --------------------------------------------------
    # PULLBACK QUALITY
    # --------------------------------------------------
    def _detect_pullback(self, bars: List[MarketBar]) -> int:

        recent = bars[-5:]
        count = 0

        for i in range(1, len(recent)):
            if abs(recent[i].close - recent[i-1].close) < (recent[i].high - recent[i].low) * 0.3:
                count += 1

        return count

    # --------------------------------------------------
    # ENTRY ZONE QUALITY
    # --------------------------------------------------
    def _detect_entry_zone(self, bars: List[MarketBar]) -> int:

        recent = bars[-5:]
        count = 0

        for i in range(1, len(recent)):
            if recent[i].low > recent[i-1].high:
                count += 1

        return count

    # --------------------------------------------------
    # SCORING MODEL
    # --------------------------------------------------
    def _entry_score(self, momentum, pullback, zone) -> float:

        score = (
            momentum * 0.5 +
            pullback * 0.2 +
            zone * 0.3
        ) / 5.0

        return min(1.0, score)

    # --------------------------------------------------
    # FINAL GATE
    # --------------------------------------------------
    def _is_allowed(self, score: float, confluence: str, liquidity: str) -> bool:

        if score < 0.5:
            return False

        if confluence == "NEUTRAL":
            return False

        if liquidity == "NEUTRAL":
            return False

        return True

    # --------------------------------------------------
    # EXPLANATIONS
    # --------------------------------------------------
    def _build_explanations(self, momentum, score, allowed):

        return [
            Explanation(
                source="M5_ENTRY_COMPRESSION",
                timeframe=Timeframe.M5,
                rule="ENTRY_SCORE",
                category="EXECUTION",
                message=f"M5 entry score: {score:.3f}",
                confidence=0.9,
                metadata={},
            ),
            Explanation(
                source="M5_ENTRY_COMPRESSION",
                timeframe=Timeframe.M5,
                rule="ALLOWED",
                category="EXECUTION",
                message=f"Entry allowed: {allowed}",
                confidence=0.95,
                metadata={},
            ),
        ]