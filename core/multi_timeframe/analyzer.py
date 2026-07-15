"""
Timeframe Analyzer.

Runs the complete analysis pipeline for a single timeframe.

Bars
  ↓
Market Structure Engine
  ↓
Price Action Engine
  ↓
TimeframeState
"""

from __future__ import annotations

from collections.abc import Sequence

from core.data.market_data import MarketBar

from core.market_structure.engine import (
    MarketStructureEngine,
)
from core.market_structure.models import (
    BOSEvent,
    CHOCHEvent,
    MarketStructureResult,
)

from core.price_action.engine import (
    PriceActionEngine,
)
from core.price_action.models import (
    PriceActionResult,
)

from .enums import (
    MarketBias,
    Timeframe,
    TimeframeAlignment,
)
from .models import (
    TimeframeState,
)


class TimeframeAnalyzer:
    """
    Executes the complete analysis pipeline for one timeframe.
    """

    def __init__(
        self,
    ) -> None:

        self.market_structure = MarketStructureEngine()

        self.price_action = PriceActionEngine()

    def reset(
        self,
    ) -> None:
        """
        Reset all underlying engines.
        """

        self.market_structure.reset()

        self.price_action.reset()

    def analyze(
        self,
        *,
        timeframe: Timeframe,
        bars: Sequence[MarketBar],
    ) -> TimeframeState:
        """
        Analyze one completed timeframe.
        """

        if not bars:
            raise ValueError(
                "bars must not be empty."
            )

        structure_result: MarketStructureResult | None = None

        #
        # Stream every completed bar through the
        # Market Structure Engine.
        #
        for bar in bars:

            structure_result = (
                self.market_structure.process(
                    bar,
                )
            )

        assert structure_result is not None

        #
        # Latest structural break.
        #
        break_event: BOSEvent | CHOCHEvent | None = (
            structure_result.last_bos
            or structure_result.last_choch
        )

        #
        # Run Price Action.
        #
        price_action_result: PriceActionResult = (
            self.price_action.process(
                bars=bars,
                break_event=break_event,
                liquidity_event=structure_result.last_liquidity,
            )
        )

        #
        # Initial bias estimation.
        #
        bias = MarketBias.NEUTRAL

        if structure_result.current_trend is not None:

            trend_name = (
                structure_result.current_trend.name
            ).upper()

            if "BULL" in trend_name:
                bias = MarketBias.BULLISH

            elif "BEAR" in trend_name:
                bias = MarketBias.BEARISH

        confidence = (
            structure_result.structure_confidence
            + price_action_result.price_action_confidence
        ) / 2.0

        return TimeframeState(
            timeframe=timeframe,
            timestamp=bars[-1].timestamp,
            bias=bias,
            alignment=TimeframeAlignment.PARTIAL,
            confidence=confidence,
            market_structure=structure_result,
            price_action=price_action_result,
        )