"""
Multi-Timeframe Engine.

Combines analysis from all configured timeframes into a
single MultiTimeframeResult.
"""

from __future__ import annotations

from datetime import datetime

from .config import MultiTimeframeConfig
from .enums import (
    MarketBias,
    TimeframeAlignment,
)
from .manager import MultiTimeframeManager
from .models import MultiTimeframeResult


class MultiTimeframeEngine:
    """
    Multi-Timeframe analysis engine.
    """

    def __init__(
        self,
        config: MultiTimeframeConfig | None = None,
    ) -> None:

        self.config = config or MultiTimeframeConfig()

    def process(
        self,
        manager: MultiTimeframeManager,
    ) -> MultiTimeframeResult:
        """
        Combine all timeframe analyses.
        """

        if not manager.is_ready():
            raise RuntimeError(
                "MultiTimeframeManager is not fully initialized."
            )

        weekly = manager.get_state(self.config.hierarchy[0])
        daily = manager.get_state(self.config.hierarchy[1])
        h4 = manager.get_state(self.config.hierarchy[2])
        h1 = manager.get_state(self.config.hierarchy[3])
        m15 = manager.get_state(self.config.hierarchy[4])
        m5 = manager.get_state(self.config.hierarchy[5])

        assert weekly is not None
        assert daily is not None
        assert h4 is not None
        assert h1 is not None
        assert m15 is not None
        assert m5 is not None

        states = (
            weekly,
            daily,
            h4,
            h1,
            m15,
            m5,
        )

        confidence = sum(
            state.confidence
            for state in states
        ) / len(states)

        bullish = sum(
            state.bias == MarketBias.BULLISH
            for state in states
        )

        bearish = sum(
            state.bias == MarketBias.BEARISH
            for state in states
        )

        if bullish > bearish:
            overall_bias = MarketBias.BULLISH
        elif bearish > bullish:
            overall_bias = MarketBias.BEARISH
        else:
            overall_bias = MarketBias.NEUTRAL

        aligned = sum(
            state.alignment == TimeframeAlignment.ALIGNED
            for state in states
        )

        if aligned == len(states):
            overall_alignment = (
                TimeframeAlignment.ALIGNED
            )
        elif aligned >= len(states) // 2:
            overall_alignment = (
                TimeframeAlignment.PARTIAL
            )
        else:
            overall_alignment = (
                TimeframeAlignment.CONFLICT
            )

        result = MultiTimeframeResult(
            weekly=weekly,
            daily=daily,
            h4=h4,
            h1=h1,
            m15=m15,
            m5=m5,
            overall_bias=overall_bias,
            overall_alignment=overall_alignment,
            confidence=confidence,
            timestamp=datetime.utcnow(),
        )

        manager.state.latest_result = result

        return result