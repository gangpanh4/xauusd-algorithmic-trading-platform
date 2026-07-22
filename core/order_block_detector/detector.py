"""Order Block detection from confirmed structural displacement."""

from __future__ import annotations

from math import isfinite
from typing import Sequence

from core.data.models import MarketBar
from core.market_structure.enums import (
    OrderBlockEventType,
    OrderBlockType,
    TrendDirection,
)
from core.market_structure.models import BOSEvent, CHOCHEvent, LiquiditySweepEvent
from core.order_block_detector.analyzer import OrderBlockAnalyzer
from core.order_block_detector.config import OrderBlockDetectorConfig
from core.order_block_detector.models import (
    OrderBlock,
    OrderBlockAnalysis,
    OrderBlockCandidate,
    OrderBlockEvent,
)
from core.order_block_detector.state import OrderBlockDetectorState
from core.order_block_detector.validator import OrderBlockValidator


class OrderBlockDetector:
    """Detect immutable Order Blocks from confirmed BOS/CHOCH events."""

    def __init__(self, config: OrderBlockDetectorConfig | None = None) -> None:
        self.config = config or OrderBlockDetectorConfig()
        self._validate_config(self.config)
        self.state = OrderBlockDetectorState()
        self.validator = OrderBlockValidator(self.config)
        # Retained for public/composition compatibility. Detection quality is
        # calculated here because it depends on candidate and trigger evidence.
        self.analyzer = OrderBlockAnalyzer()

    def reset(self) -> None:
        self.state.reset()

    def process(
        self,
        *,
        break_event: BOSEvent | CHOCHEvent | None,
        bars: Sequence[MarketBar] | None = None,
        liquidity_event: LiquiditySweepEvent | None = None,
    ) -> OrderBlockEvent | None:
        """Process one confirmed structural break exactly once."""

        self.state.processed_break_count += 1
        if break_event is None:
            return None

        self._validate_break_event(break_event)
        validated_bars = self._validate_bars(bars or ())

        if self._has_processed_break(break_event):
            return None

        candidate = self._create_candidate(
            break_event=break_event,
            bars=validated_bars,
            liquidity_event=liquidity_event,
        )
        self._store_candidate(candidate)

        if not self.validator.validate(candidate):
            self._remove_pending_candidate(candidate)
            return None

        order_block = self._confirm_candidate(candidate)
        analysis = self._analyze_candidate(candidate)
        if analysis.total_score < self.config.minimum_strength:
            self._remove_pending_candidate(candidate)
            return None

        if not self.config.allow_nested_blocks and self._overlaps_active(order_block):
            self._remove_pending_candidate(candidate)
            return None

        event = self._create_event(order_block, analysis)
        self._remove_pending_candidate(candidate)
        self.state.confirmed_order_blocks.append(order_block)
        self.state.active_order_blocks.append(order_block)
        self.state.confirmed_events.append(event)
        self.state.last_event = event
        self.state.next_block_id += 1
        return event

    def get_state(self) -> OrderBlockDetectorState:
        return self.state

    def get_order_blocks(self) -> list[OrderBlock]:
        return self.state.confirmed_order_blocks

    def get_active_order_blocks(self) -> list[OrderBlock]:
        return self.state.active_order_blocks

    def get_last_event(self) -> OrderBlockEvent | None:
        return self.state.last_event

    def get_last_candidate(self) -> OrderBlockCandidate | None:
        return self.state.pending_candidates[-1] if self.state.pending_candidates else None

    def _find_origin_bar(
        self,
        *,
        break_event: BOSEvent | CHOCHEvent,
        bars: Sequence[MarketBar],
    ) -> MarketBar | None:
        """Return the nearest opposite candle preceding the break candle."""

        bullish = break_event.direction is TrendDirection.BULLISH
        eligible = (
            bar
            for bar in reversed(bars)
            if bar.timestamp <= break_event.timestamp
        )
        for bar in eligible:
            if bullish and bar.is_bearish:
                return bar
            if not bullish and bar.is_bullish:
                return bar
        return None

    def _score_origin_bar(self, bar: MarketBar) -> float:
        """Return a normalized origin-candle quality score in ``[0, 1]``."""

        if bar.range_size <= 0.0:
            return 0.0
        body_quality = bar.body_ratio
        wick_balance = 1.0 - min(1.0, (bar.upper_wick + bar.lower_wick) / bar.range_size)
        return self._clamp((0.75 * body_quality) + (0.25 * wick_balance))

    def _create_candidate(
        self,
        *,
        break_event: BOSEvent | CHOCHEvent,
        bars: Sequence[MarketBar],
        liquidity_event: LiquiditySweepEvent | None,
    ) -> OrderBlockCandidate:
        if break_event.direction is TrendDirection.BULLISH:
            block_type = OrderBlockType.BULLISH
        elif break_event.direction is TrendDirection.BEARISH:
            block_type = OrderBlockType.BEARISH
        else:
            raise ValueError("Order Block requires bullish or bearish break direction")

        origin_bar = self._find_origin_bar(break_event=break_event, bars=bars)
        if origin_bar is None:
            top_price = max(break_event.break_price, break_event.swing_point.price)
            bottom_price = min(break_event.break_price, break_event.swing_point.price)
            origin_score = 0.0
            timestamp = break_event.timestamp
        else:
            top_price = origin_bar.high
            bottom_price = origin_bar.low
            origin_score = self._score_origin_bar(origin_bar)
            timestamp = origin_bar.timestamp

        return OrderBlockCandidate(
            timestamp=timestamp,
            block_type=block_type,
            top_price=top_price,
            bottom_price=bottom_price,
            origin_swing=break_event.swing_point,
            trigger_break=break_event,
            trigger_liquidity=liquidity_event,
            creation_index=break_event.confirmation_index,
            origin_bar_score=origin_score,
        )

    def _confirm_candidate(self, candidate: OrderBlockCandidate) -> OrderBlock:
        return OrderBlock(
            timestamp=candidate.timestamp,
            block_type=candidate.block_type,
            top_price=candidate.top_price,
            bottom_price=candidate.bottom_price,
            origin_swing=candidate.origin_swing,
            trigger_break=candidate.trigger_break,
            trigger_liquidity=candidate.trigger_liquidity,
            creation_index=candidate.creation_index,
            confirmation_index=candidate.trigger_break.confirmation_index,
        )

    def _analyze_candidate(self, candidate: OrderBlockCandidate) -> OrderBlockAnalysis:
        break_event = candidate.trigger_break
        structure_values = [
            self._clamp(float(getattr(break_event, name, 0.0)))
            for name in ("quality", "strength", "structure_score")
            if isfinite(float(getattr(break_event, name, 0.0)))
        ]
        structure_score = sum(structure_values) / len(structure_values)

        atr_multiple = max(0.0, float(getattr(break_event, "break_atr_multiple", 0.0)))
        if atr_multiple > 0.0:
            displacement_score = self._clamp(atr_multiple / 2.0)
        else:
            block_height = max(candidate.top_price - candidate.bottom_price, 1e-12)
            distance = max(0.0, float(getattr(break_event, "break_distance", 0.0)))
            displacement_score = self._clamp(distance / block_height)

        liquidity_score = 0.0
        if self.config.enable_liquidity_bonus and candidate.trigger_liquidity is not None:
            liquidity = candidate.trigger_liquidity
            liquidity_score = self._clamp(
                sum(
                    self._clamp(float(getattr(liquidity, name, 0.0)))
                    for name in ("quality", "sweep_strength", "reaction_strength", "reclaim_strength")
                ) / 4.0
            )

        reaction_score = self._clamp(candidate.origin_bar_score)
        weighted_total = (
            (0.40 * structure_score)
            + (0.35 * displacement_score)
            + (0.15 * reaction_score)
            + (0.10 * liquidity_score)
        )
        return OrderBlockAnalysis(
            structure_score=structure_score,
            displacement_score=displacement_score,
            liquidity_score=liquidity_score,
            reaction_score=reaction_score,
            total_score=self._clamp(weighted_total),
        )

    def _create_event(self, order_block: OrderBlock, analysis: OrderBlockAnalysis) -> OrderBlockEvent:
        return OrderBlockEvent(
            timestamp=order_block.timestamp,
            event_type=OrderBlockEventType.CREATED,
            order_block=order_block,
            analysis=analysis,
            confirmation_index=order_block.confirmation_index,
        )

    def _store_candidate(self, candidate: OrderBlockCandidate) -> None:
        self.state.pending_candidates.append(candidate)

    def _remove_pending_candidate(self, candidate: OrderBlockCandidate) -> None:
        if candidate in self.state.pending_candidates:
            self.state.pending_candidates.remove(candidate)

    def _has_processed_break(self, break_event: BOSEvent | CHOCHEvent) -> bool:
        return any(
            self._same_break(block.trigger_break, break_event)
            for block in self.state.confirmed_order_blocks
        ) or any(
            self._same_break(candidate.trigger_break, break_event)
            for candidate in self.state.pending_candidates
        )

    @staticmethod
    def _same_break(left: BOSEvent | CHOCHEvent, right: BOSEvent | CHOCHEvent) -> bool:
        return (
            type(left) is type(right)
            and left.timestamp == right.timestamp
            and left.confirmation_index == right.confirmation_index
            and left.direction is right.direction
            and left.swing_point.timestamp == right.swing_point.timestamp
            and left.swing_point.price == right.swing_point.price
        )

    def _overlaps_active(self, candidate: OrderBlock) -> bool:
        return any(
            block.block_type is candidate.block_type
            and max(block.bottom_price, candidate.bottom_price)
            <= min(block.top_price, candidate.top_price)
            for block in self.state.active_order_blocks
        )

    @staticmethod
    def _validate_config(config: OrderBlockDetectorConfig) -> None:
        if config.minimum_displacement < 0.0:
            raise ValueError("minimum_displacement must be non-negative")
        if config.minimum_block_height <= 0.0:
            raise ValueError("minimum_block_height must be positive")
        if not 0.0 <= config.minimum_strength <= 1.0:
            raise ValueError("minimum_strength must be between 0 and 1")
        if config.maximum_block_age <= 0:
            raise ValueError("maximum_block_age must be positive")

    @staticmethod
    def _validate_break_event(break_event: BOSEvent | CHOCHEvent) -> None:
        if break_event.direction not in (TrendDirection.BULLISH, TrendDirection.BEARISH):
            raise ValueError("break direction must be bullish or bearish")
        if break_event.confirmation_index < break_event.swing_point.confirmation_index:
            raise ValueError("break confirmation cannot precede swing confirmation")
        for value in (break_event.break_price, break_event.swing_point.price):
            if not isfinite(float(value)):
                raise ValueError("break prices must be finite")

    @staticmethod
    def _validate_bars(bars: Sequence[MarketBar]) -> tuple[MarketBar, ...]:
        validated: list[MarketBar] = []
        previous_timestamp = None
        for bar in bars:
            if not isinstance(bar, MarketBar):
                raise TypeError("bars must contain MarketBar instances")
            if bar.timestamp.tzinfo is None or bar.timestamp.utcoffset() is None:
                raise ValueError("bar timestamps must be timezone-aware")
            if previous_timestamp is not None and bar.timestamp <= previous_timestamp:
                raise ValueError("bar timestamps must be strictly increasing")
            values = (bar.open, bar.high, bar.low, bar.close)
            if not all(isfinite(float(value)) for value in values):
                raise ValueError("bar prices must be finite")
            if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close):
                raise ValueError("invalid candle geometry")
            if bar.high < bar.low:
                raise ValueError("bar high cannot be below low")
            validated.append(bar)
            previous_timestamp = bar.timestamp
        return tuple(validated)

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, value))
