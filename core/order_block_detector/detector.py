"""
Order Block Detection Engine.
"""

from __future__ import annotations

from typing import Any

MarketBar = Any

from core.market_structure.enums import (
    MarketTrend,
    OrderBlockType,
)

from core.market_structure.models import (
    BOSEvent,
    CHOCHEvent,
    LiquiditySweepEvent,
)

from core.order_block_detector.config import (
    OrderBlockDetectorConfig,
)

from core.order_block_detector.models import (
    OrderBlock,
    OrderBlockCandidate,
    OrderBlockEvent,
)

from core.order_block_detector.state import (
    OrderBlockDetectorState,
)


class OrderBlockDetector:
    """
    Detects institutional Order Blocks from confirmed
    market structure events.

    Version 3

    - Candidate creation
    - Candidate validation
    - Candidate storage

    Confirmation, mitigation, invalidation and lifecycle
    handling are implemented in later stages.
    """

    def __init__(
        self,
        config: OrderBlockDetectorConfig | None = None,
    ) -> None:

        self.config = config or OrderBlockDetectorConfig()

        self.state = OrderBlockDetectorState()

    def reset(
        self,
    ) -> None:
        """
        Reset detector runtime state.
        """

        self.state.reset()

    def process(
        self,
        *,
        break_event: BOSEvent | CHOCHEvent | None,
        bars: list[MarketBar] | None = None,
        liquidity_event: LiquiditySweepEvent | None = None,
    ) -> OrderBlockCandidate | None:
        """
        Process one confirmed structural break.

        Returns:
            The validated Order Block candidate.

        Version 3 performs:

        - Candidate creation
        - Candidate validation
        - Candidate storage
        - Candidate return
        """

        self.state.processed_break_count += 1

        if break_event is None:
            return None

        candidate = self._create_candidate(
            break_event=break_event,
            bars=bars or [],
            liquidity_event=liquidity_event,
        )

        if candidate is None:
            return None

        if not self._validate_candidate(candidate):
            return None

        self._store_candidate(candidate)

        return candidate

    def get_state(
        self,
    ) -> OrderBlockDetectorState:
        """
        Return detector runtime state.
        """

        return self.state

    def get_order_blocks(
        self,
    ) -> list[OrderBlock]:
        """
        Return confirmed Order Blocks.
        """

        return self.state.confirmed_order_blocks

    def get_active_order_blocks(
        self,
    ) -> list[OrderBlock]:
        """
        Return active Order Blocks.
        """

        return self.state.active_order_blocks

    def get_last_event(
        self,
    ) -> OrderBlockEvent | None:
        """
        Return the most recent lifecycle event.
        """

        return self.state.last_event

    def get_last_candidate(
        self,
    ) -> OrderBlockCandidate | None:
        """
        Return the most recently created candidate.
        """

        if not self.state.pending_candidates:
            return None

        return self.state.pending_candidates[-1]

    def _find_origin_bar(
        self,
        *,
        break_event: BOSEvent | CHOCHEvent,
        bars: list[MarketBar],
    ) -> MarketBar | None:
        """
        Find the highest-quality origin candle.

        Version 2 scores opposite-colored candles instead
        of simply returning the first one encountered.
        """

        if not bars:
            return None

        bullish = (
            break_event.direction.name == "BULLISH"
        )

        best_bar: MarketBar | None = None
        best_score = float("-inf")

        for bar in reversed(bars):

            # Candidate polarity

            if bullish:

                if bar.close >= bar.open:
                    continue

            else:

                if bar.close <= bar.open:
                    continue

            score = self._score_origin_bar(bar)

            if score > best_score:
                best_score = score
                best_bar = bar

        return best_bar

    def _score_origin_bar(
        self,
        bar: MarketBar,
    ) -> float:
        """
        Score an origin candle.

        Higher score = better institutional
        Order Block origin.
        """

        score = 0.0

        # Larger candle body

        score += bar.body_size

        # Prefer small upper wick

        score -= bar.upper_wick * 0.25

        # Prefer small lower wick

        score -= bar.lower_wick * 0.25

        # Slight preference for larger range

        score += bar.range_size * 0.10

        return score

    def _create_candidate(
        self,
        *,
        break_event: BOSEvent | CHOCHEvent,
        bars: list[MarketBar],
        liquidity_event: LiquiditySweepEvent | None,
    ) -> OrderBlockCandidate:
        """
        Create an Order Block candidate from a confirmed
        structural break.
        """

        if break_event.direction is MarketTrend.BULLISH:
            block_type = OrderBlockType.BULLISH

        elif break_event.direction is MarketTrend.BEARISH:
            block_type = OrderBlockType.BEARISH

        else:
            raise ValueError(
                "Unsupported market trend."
            )

        origin_bar = self._find_origin_bar(
            break_event=break_event,
            bars=bars,
        )

        origin_bar_score = 0.0

        if origin_bar is not None:
            origin_bar_score = (
                self._score_origin_bar(
                    origin_bar,
                )
            )

        top_price = break_event.break_price
        bottom_price = break_event.swing_point.price

        if origin_bar is not None:
            top_price = origin_bar.high
            bottom_price = origin_bar.low

        return OrderBlockCandidate(
            timestamp=break_event.timestamp,
            block_type=block_type,
            top_price=top_price,
            bottom_price=bottom_price,
            origin_swing=break_event.swing_point,
            trigger_break=break_event,
            trigger_liquidity=liquidity_event,
            creation_index=break_event.confirmation_index,
            origin_bar_score=origin_bar_score,
        )

    def _validate_candidate(
        self,
        candidate: OrderBlockCandidate,
    ) -> bool:
        """
        Validate a candidate before it enters the detector
        runtime state.
        """

        if candidate.top_price < candidate.bottom_price:
            return False

        if candidate.origin_swing is None:
            return False

        if candidate.trigger_break is None:
            return False

        return True

    def _store_candidate(
        self,
        candidate: OrderBlockCandidate,
    ) -> None:
        """
        Store a validated Order Block candidate.
        """

        self.state.pending_candidates.append(candidate)