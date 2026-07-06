from __future__ import annotations

from typing import List

from core.trading_pipeline.models import MarketBar
from core.intelligence.contracts.liquidity_state import LiquidityState
from core.intelligence.contracts.explanation import Explanation
from core.intelligence.contracts.enums import Timeframe


class LiquidityEngine:
    """
    Sprint 3 — Liquidity + Structure Interaction Engine (v2)

    UPGRADE:
        Moves from static liquidity detection → behavioral liquidity model
    """

    def __init__(self, symbol: str):
        self.symbol = symbol

    # --------------------------------------------------
    # MAIN ENTRY
    # --------------------------------------------------
    def process(self, bars: List[MarketBar]) -> LiquidityState:
        if not bars or len(bars) < 50:
            return self._invalid(bars)

        sweeps = self._detect_sweeps(bars)
        bos = self._detect_bos(bars)
        mitigation = self._detect_mitigation(bars)
        structure_score = self._structure_liquidity_alignment(
            sweeps,
            bos,
            mitigation,
        )
        tradable = self._is_tradable(sweeps, bos, structure_score)
        explanations = self._build_explanations(
            sweeps,
            bos,
            mitigation,
            structure_score,
            tradable,
        )
        return LiquidityState(
            timestamp=bars[-1].timestamp,
            symbol=self.symbol,
            timeframe=Timeframe.M15,
            engine_version="LiquidityStructureEngine-2.0.0",
            sweeps=sweeps,
            bos=bos,
            fvg_zones=mitigation,
            liquidity_score=structure_score,
            tradable_zone=tradable,
            confidence=min(1.0, structure_score),
            explanations=tuple(explanations),
            metadata={
                "mode": "liquidity_structure_interaction",
            },
        )

    # --------------------------------------------------
    # 1. LIQUIDITY SWEEP DETECTION
    # --------------------------------------------------
    def _detect_sweeps(self, bars: List[MarketBar]) -> int:
        recent = bars[-20:]
        count = 0
        for i in range(2, len(recent)):
            # sweep high then rejection
            if recent[i].high > recent[i - 1].high and recent[i].close < recent[i].high:
                count += 1
            # sweep low then rejection
            if recent[i].low < recent[i - 1].low and recent[i].close > recent[i].low:
                count += 1
        return count

    # --------------------------------------------------
    # 2. STRUCTURE BREAK (BOS)
    # --------------------------------------------------
    def _detect_bos(self, bars: List[MarketBar]) -> int:
        recent = bars[-20:]
        bos = 0
        for i in range(2, len(recent)):
            if recent[i].close > recent[i - 1].high:
                bos += 1
            if recent[i].close < recent[i - 1].low:
                bos += 1
        return bos

    # --------------------------------------------------
    # 3. LIQUIDITY MITIGATION (FVG RETURN)
    # --------------------------------------------------
    def _detect_mitigation(self, bars: List[MarketBar]) -> int:
        recent = bars[-15:]
        count = 0
        for i in range(2, len(recent)):
            # imbalance fill
            if recent[i].low <= recent[i - 2].high:
                count += 1
        return count

    # --------------------------------------------------
    # 4. STRUCTURE-LIQUIDITY ALIGNMENT SCORE
    # --------------------------------------------------
    def _structure_liquidity_alignment(
        self,
        sweeps: int,
        bos: int,
        mitigation: int,
    ) -> float:
        # 🔥 weighted institutional behavior model
        score = (
            sweeps * 0.4 +
            bos * 0.4 +
            mitigation * 0.2
        ) / 10.0
        return min(1.0, score)

    # --------------------------------------------------
    # 5. TRADE VALIDATION LOGIC
    # --------------------------------------------------
    def _is_tradable(
        self,
        sweeps: int,
        bos: int,
        score: float,
    ) -> bool:
        # ❗ REAL EDGE CONDITION
        if sweeps < 2:
            return False
        if bos < 1:
            return False
        if score < 0.35:
            return False
        return True

    # --------------------------------------------------
    # 6. EXPLANATIONS
    # --------------------------------------------------
    def _build_explanations(
        self,
        sweeps: int,
        bos: int,
        mitigation: int,
        score: float,
        tradable: bool,
    ) -> List[Explanation]:
        return [
            Explanation(
                source="LIQUIDITY_STRUCTURE_ENGINE",
                timeframe=Timeframe.M15,
                rule="SWEEPS",
                category="ALPHA",
                message=f"Liquidity sweeps: {sweeps}",
                confidence=0.85,
                metadata={},
            ),
            Explanation(
                source="LIQUIDITY_STRUCTURE_ENGINE",
                timeframe=Timeframe.M15,
                rule="BOS",
                category="ALPHA",
                message=f"BOS events: {bos}",
                confidence=0.85,
                metadata={},
            ),
            Explanation(
                source="LIQUIDITY_STRUCTURE_ENGINE",
                timeframe=Timeframe.M15,
                rule="ALIGNMENT",
                category="ALPHA",
                message=f"Structure-Liquidity score: {score:.3f} | Tradable: {tradable}",
                confidence=0.9,
                metadata={},
            ),
        ]

    # --------------------------------------------------
    # FALLBACK
    # --------------------------------------------------
    def _invalid(self, bars: List[MarketBar]) -> LiquidityState:
        return LiquidityState(
            timestamp=bars[-1].timestamp if bars else None,
            symbol=self.symbol,
            timeframe=Timeframe.M15,
            engine_version="LiquidityStructureEngine-2.0.0",
            sweeps=0,
            bos=0,
            fvg_zones=0,
            liquidity_score=0.0,
            tradable_zone=False,
            confidence=0.0,
            explanations=(),
            metadata={"reason": "insufficient_data"},
        )