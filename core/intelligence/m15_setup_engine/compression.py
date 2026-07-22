from __future__ import annotations

from typing import List

from core.trading_pipeline.models import MarketBar
from core.intelligence.contracts.setup_state import SetupState
from core.intelligence.contracts.explanation import Explanation
from core.intelligence.contracts.enums import Timeframe


class M15SetupCompressionEngine:
    """
    Sprint 3 — M15 Setup Compression Engine

    PURPOSE:
        Filter out weak setups and keep ONLY institutional-grade displacement setups.

    KEY IDEA:
        Not every setup is tradable.
        Only displacement + imbalance + alignment matters.
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
    ) -> SetupState:

        displacement = self._detect_displacement(bars)
        imbalance = self._detect_imbalance(bars)
        retracement_quality = self._detect_retracement(bars)

        score = self._setup_score(
            displacement,
            imbalance,
            retracement_quality,
        )

        allowed = self._is_allowed(
            score,
            confluence_direction,
            liquidity_bias,
        )

        explanations = self._build_explanations(
            displacement,
            imbalance,
            score,
            allowed,
        )

        return SetupState(
            timestamp=bars[-1].timestamp,
            symbol=self.symbol,
            timeframe=Timeframe.M15,
            engine_version="M15CompressionEngine-1.0.0",
            displacement=displacement,
            imbalance=imbalance,
            retracement_quality=retracement_quality,
            score=score,
            allowed=allowed,
            confidence=min(1.0, score),
            explanations=tuple(explanations),
            metadata={
                "mode": "setup_compression",
            },
        )

    # --------------------------------------------------
    # DISPLACEMENT DETECTION
    # --------------------------------------------------
    def _detect_displacement(self, bars: List[MarketBar]) -> int:

        recent = bars[-10:]
        count = 0

        for i in range(2, len(recent)):
            body = abs(recent[i].close - recent[i].open)
            range_size = recent[i].high - recent[i].low

            if range_size > 0 and body / range_size > 0.6:
                count += 1

        return count

    # --------------------------------------------------
    # IMBALANCE DETECTION (FVG STYLE)
    # --------------------------------------------------
    def _detect_imbalance(self, bars: List[MarketBar]) -> int:

        recent = bars[-10:]
        count = 0

        for i in range(2, len(recent)):
            if recent[i].low > recent[i-2].high:
                count += 1

        return count

    # --------------------------------------------------
    # RETRACEMENT QUALITY
    # --------------------------------------------------
    def _detect_retracement(self, bars: List[MarketBar]) -> int:

        recent = bars[-10:]
        count = 0

        for i in range(1, len(recent)):
            if abs(recent[i].close - recent[i-1].close) < (recent[i].high - recent[i].low) * 0.3:
                count += 1

        return count

    # --------------------------------------------------
    # SETUP SCORING
    # --------------------------------------------------
    def _setup_score(self, displacement, imbalance, retracement) -> float:

        score = (
            displacement * 0.5 +
            imbalance * 0.3 +
            retracement * 0.2
        ) / 5.0

        return min(1.0, score)

    # --------------------------------------------------
    # FINAL FILTER (STRICT)
    # --------------------------------------------------
    def _is_allowed(self, score: float, confluence: str, liquidity: str) -> bool:

        if score < 0.45:
            return False

        if confluence == "NEUTRAL":
            return False

        if liquidity == "NEUTRAL":
            return False

        return True

    # --------------------------------------------------
    # EXPLANATIONS
    # --------------------------------------------------
    def _build_explanations(self, disp, imb, score, allowed):

        return [
            Explanation(
                source="M15_COMPRESSION_ENGINE",
                timeframe=Timeframe.M15,
                rule="SETUP_SCORE",
                category="ALPHA",
                message=f"Setup score: {score:.3f}",
                confidence=0.9,
                metadata={},
            ),
            Explanation(
                source="M15_COMPRESSION_ENGINE",
                timeframe=Timeframe.M15,
                rule="ALLOWED",
                category="ALPHA",
                message=f"Allowed: {allowed}",
                confidence=0.95,
                metadata={},
            ),
        ]