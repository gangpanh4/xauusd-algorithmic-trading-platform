from __future__ import annotations

from typing import List

from core.data.models import MarketBar
from core.intelligence.contracts.market_regime import MarketRegime
from core.intelligence.contracts.explanation import Explanation
from core.intelligence.contracts.enums import Timeframe


class MarketRegimeEngine:
    """
    Market Regime Engine (Sprint 2 - Missing Alpha Layer)

    Purpose:
        Detect market environment quality BEFORE any trade decision.

    Key Idea:
        We do NOT trade all conditions.
        We filter bad environments first.
    """

    def __init__(self, symbol: str):
        self.symbol = symbol

    # --------------------------------------------------
    # MAIN ENTRY
    # --------------------------------------------------
    def process(self, bars: List[MarketBar]) -> MarketRegime:

        if not bars or len(bars) < 20:
            return self._invalid(bars)

        volatility = self._volatility(bars)
        directionality = self._directionality(bars)
        range_score = self._range_score(bars)

        regime = self._classify(
            volatility,
            directionality,
            range_score,
        )

        tradable = self._is_tradable(regime)

        explanations = self._build_explanations(
            volatility,
            directionality,
            range_score,
            regime,
            tradable,
        )

        return MarketRegime(
            timestamp=bars[-1].timestamp,
            symbol=self.symbol,
            timeframe=Timeframe.H1,
            engine_version="MarketRegimeEngine-1.0.0",
            regime=regime,
            tradable=tradable,
            confidence=self._confidence(volatility, directionality, range_score),
            explanations=tuple(explanations),
            metadata={
                "volatility": volatility,
                "directionality": directionality,
                "range_score": range_score,
            },
        )

    # --------------------------------------------------
    # METRICS
    # --------------------------------------------------
    def _volatility(self, bars: List[MarketBar]) -> float:
        recent = bars[-20:]
        return sum(b.high - b.low for b in recent) / len(recent)

    def _directionality(self, bars: List[MarketBar]) -> float:
        recent = bars[-10:]
        up = sum(1 for i in range(1, len(recent)) if recent[i].close > recent[i - 1].close)
        down = sum(1 for i in range(1, len(recent)) if recent[i].close < recent[i - 1].close)

        return abs(up - down) / max(1, len(recent))

    def _range_score(self, bars: List[MarketBar]) -> float:
        recent = bars[-20:]
        high = max(b.high for b in recent)
        low = min(b.low for b in recent)

        avg_body = sum(abs(b.close - b.open) for b in recent) / len(recent)

        return (high - low) / (avg_body + 1e-6)

    # --------------------------------------------------
    # CLASSIFICATION
    # --------------------------------------------------
    def _classify(self, vol: float, dir_: float, rng: float) -> str:

        if rng < 2 and dir_ > 0.3:
            return "TRENDING"

        if rng > 5 and dir_ < 0.2:
            return "RANGING"

        if vol < 1:
            return "CONTRACTING"

        if vol > 3 and rng > 4:
            return "EXPANDING"

        return "CHOPPY"

    # --------------------------------------------------
    # TRADE FILTER
    # --------------------------------------------------
    def _is_tradable(self, regime: str) -> bool:

        return regime in ["TRENDING", "EXPANDING"]

    # --------------------------------------------------
    # CONFIDENCE
    # --------------------------------------------------
    def _confidence(self, vol: float, dir_: float, rng: float) -> float:
        return min(1.0, (vol + dir_ + (1 / (rng + 1e-6))) / 3)

    # --------------------------------------------------
    # EXPLANATIONS
    # --------------------------------------------------
    def _build_explanations(
        self,
        vol: float,
        dir_: float,
        rng: float,
        regime: str,
        tradable: bool,
    ) -> List[Explanation]:

        return [
            Explanation(
                source="REGIME_ENGINE",
                timeframe=Timeframe.H1,
                rule="VOLATILITY",
                category="REGIME",
                message=f"Volatility: {vol:.2f}",
                confidence=0.7,
                metadata={},
            ),
            Explanation(
                source="REGIME_ENGINE",
                timeframe=Timeframe.H1,
                rule="REGIME_CLASSIFICATION",
                category="REGIME",
                message=f"Regime: {regime} | Tradable: {tradable}",
                confidence=0.8,
                metadata={},
            ),
        ]

    # --------------------------------------------------
    # FALLBACK
    # --------------------------------------------------
    def _invalid(self, bars: List[MarketBar]) -> MarketRegime:

        return MarketRegime(
            timestamp=bars[-1].timestamp if bars else None,
            symbol=self.symbol,
            timeframe=Timeframe.H1,
            engine_version="MarketRegimeEngine-1.0.0",
            regime="CHOPPY",
            tradable=False,
            confidence=0.0,
            explanations=(),
            metadata={"reason": "insufficient_data"},
        )