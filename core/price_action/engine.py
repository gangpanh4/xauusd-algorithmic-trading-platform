"""
Price Action Engine.
"""

from __future__ import annotations

from core.market_structure.models import (
    BOSEvent,
    CHOCHEvent,
    LiquiditySweepEvent,
)

from core.order_block_detector.detector import (
    OrderBlockDetector,
)

from core.fair_value_gap_detector.detector import (
    FairValueGapDetector,
)

from .models import (
    PriceActionResult,
)


class PriceActionEngine:
    """
    High-level Price Action Engine.

    Coordinates all price-action detectors.

    BOS / CHOCH
           │
           ▼
      Order Block

    Bars
           │
           ▼
      Fair Value Gap
    """

    def __init__(
        self,
    ) -> None:

        self.order_block_detector = (
            OrderBlockDetector()
        )

        self.fair_value_gap_detector = (
            FairValueGapDetector()
        )

    def reset(
        self,
    ) -> None:

        self.order_block_detector.reset()

        self.fair_value_gap_detector.reset()

    def process(
        self,
        *,
        bars,
        break_event: BOSEvent | CHOCHEvent | None,
        liquidity_event: LiquiditySweepEvent | None,
    ) -> PriceActionResult:
        """
        Process price-action detectors.
        """

        if break_event is not None:

            self.order_block_detector.process(
                break_event=break_event,
                liquidity_event=liquidity_event,
            )

        self.fair_value_gap_detector.process(
            bars,
        )

        return PriceActionResult(
            timestamp=bars[-1].timestamp,
            last_order_block=self._last_order_block(),
            last_fair_value_gap=self._last_fvg(),
            price_action_confidence=self._confidence(),
        )

    def _last_order_block(
        self,
    ):

        blocks = (
            self.order_block_detector.get_blocks()
        )

        if not blocks:
            return None

        return blocks[-1]

    def _last_fvg(
        self,
    ):

        gaps = (
            self.fair_value_gap_detector.state.active_gaps
        )

        if not gaps:
            return None

        return gaps[-1]

    def _confidence(
        self,
    ) -> float:
        """
        Initial confidence calculation.
        """

        score = 0.0

        if self._last_order_block() is not None:
            score += 0.5

        if self._last_fvg() is not None:
            score += 0.5

        return score