"""
Market Structure Engine.

Coordinates all market structure detectors and exposes a single
high-level interface to the rest of the trading platform.
"""

from __future__ import annotations

from core.data.market_data import MarketBar

from core.market_structure.bos_detector import BOSDetector
from core.market_structure.choch_detector import CHOCHDetector
from core.market_structure.config import (
    MarketStructureConfig,
)
from core.market_structure.liquidity_detector import LiquidityDetector
from core.market_structure.models import (
    MarketStructureResult,
)
from core.market_structure.swing_detector import SwingDetector


class MarketStructureEngine:
    """
    High-level Market Structure Engine.

    Owns all market structure detectors and executes them
    in dependency order.

    Bar
      ↓
    Swing
      ↓
    BOS
      ↓
    CHOCH
      ↓
    Liquidity
    """

    def __init__(
        self,
        config: MarketStructureConfig | None = None,
    ) -> None:

        self.config = config or MarketStructureConfig()

        self.swing_detector = SwingDetector()

        self.bos_detector = BOSDetector()

        self.choch_detector = CHOCHDetector(
            bos_state=self.bos_detector.state,
        )

        self.liquidity_detector = LiquidityDetector()

    def reset(
        self,
    ) -> None:
        """
        Reset all detector state.
        """

        self.swing_detector.reset()

        self.bos_detector.reset()

        self.choch_detector.reset()

        self.liquidity_detector.reset()

    def process(
        self,
        bar: MarketBar,
    ) -> MarketStructureResult:
        """
        Process one completed market bar.
        """

        print(f"MARKET STRUCTURE PROCESS: {bar.timestamp}")

        swing = self.swing_detector.process(bar)

        if swing is not None:
            print(
                f"SWING GENERATED: "
                f"{swing.swing_type} "
                f"{swing.price}"
            )

        bos = None
        choch = None
        liquidity = None

        if swing is not None:

            bos = self.bos_detector.process(
                swing,
            )

            if bos is not None:
                print(
                    f"BOS GENERATED: "
                    f"{bos.direction} "
                    f"{bos.break_price}"
                )

            choch = self.choch_detector.process(
                swing,
            )

            liquidity = self.liquidity_detector.process(
                swing,
            )

        return MarketStructureResult(
            timestamp=bar.timestamp,
            last_swing=self.swing_detector.get_last_swing(),
            last_bos=self.bos_detector.get_last_break(),
            last_choch=self.choch_detector.state.last_change,
            last_liquidity=self.liquidity_detector.get_last_sweep(),
            current_trend=self.bos_detector.state.current_trend,
            structure_confidence=self._calculate_confidence(),
        )

    def _calculate_confidence(
        self,
    ) -> float:
        """
        Calculate market structure confidence.

        Version 2 uses configurable weights instead of
        fixed contributions so the confidence model can
        be optimized through research and backtesting.
        """

        score = 0.0

        if self.swing_detector.get_last_swing() is not None:
            score += self.config.swing_confidence_weight

        if self.bos_detector.get_last_break() is not None:
            score += self.config.bos_confidence_weight

        if self.choch_detector.state.last_change is not None:
            score += self.config.choch_confidence_weight

        if self.liquidity_detector.get_last_sweep() is not None:
            score += self.config.liquidity_confidence_weight

        return (
            score
            / self.config.maximum_confidence_score
        )