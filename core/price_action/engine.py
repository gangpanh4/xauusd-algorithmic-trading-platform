"""Price-action orchestration.

The engine coordinates Order Block and Fair Value Gap detection without owning
those detectors' domain lifecycles.  It validates completed bars, prevents
reprocessing the same structural/FVG event, selects the newest usable evidence,
and derives confidence from evidence quality, freshness, and directional
agreement.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from math import isfinite
from typing import Any

from core.data.models import MarketBar
from core.fair_value_gap_detector.detector import FairValueGapDetector
from core.fair_value_gap_detector.models import FairValueGap, FairValueGapCandidate
from core.market_structure.models import BOSEvent, CHOCHEvent, LiquiditySweepEvent
from core.order_block_detector.detector import OrderBlockDetector
from core.order_block_detector.models import OrderBlock, OrderBlockEvent

from .models import PriceActionResult


class PriceActionEngine:
    """Coordinate price-action detectors for one chronological timeframe.

    ``PriceActionEngine`` is intentionally stateful because its detectors are
    stateful.  One engine instance must therefore belong to exactly one
    timeframe.  The multi-timeframe coordinator enforces that ownership.
    """

    _ORDER_BLOCK_WEIGHT = 0.60
    _FAIR_VALUE_GAP_WEIGHT = 0.40
    _CONFLICT_MULTIPLIER = 0.50

    def __init__(
        self,
        *,
        order_block_detector: OrderBlockDetector | None = None,
        fair_value_gap_detector: FairValueGapDetector | None = None,
        freshness_half_life_bars: int = 8,
        maximum_evidence_age_bars: int = 32,
    ) -> None:
        self._validate_positive_integer(
            freshness_half_life_bars,
            field_name="freshness_half_life_bars",
        )
        self._validate_positive_integer(
            maximum_evidence_age_bars,
            field_name="maximum_evidence_age_bars",
        )
        if maximum_evidence_age_bars < freshness_half_life_bars:
            raise ValueError(
                "maximum_evidence_age_bars must be at least "
                "freshness_half_life_bars"
            )

        self.order_block_detector = order_block_detector or OrderBlockDetector()
        self.fair_value_gap_detector = (
            fair_value_gap_detector or FairValueGapDetector()
        )
        self.freshness_half_life_bars = freshness_half_life_bars
        self.maximum_evidence_age_bars = maximum_evidence_age_bars

        self._processed_break_keys: set[tuple[Any, ...]] = set()
        self._processed_fvg_windows: set[tuple[datetime, datetime, datetime]] = set()

    def reset(self) -> None:
        """Reset all owned detector and de-duplication state."""

        self.order_block_detector.reset()
        self.fair_value_gap_detector.reset()
        self._processed_break_keys.clear()
        self._processed_fvg_windows.clear()

    def process(
        self,
        *,
        bars: Sequence[MarketBar],
        break_event: BOSEvent | CHOCHEvent | None,
        liquidity_event: LiquiditySweepEvent | None,
    ) -> PriceActionResult:
        """Process one completed chronological bar window.

        The full validated bar window is supplied to Order Block detection so
        the detector can identify the displacement origin candle.  Fair Value
        Gap detection receives each unique final three-bar window exactly once.
        """

        validated_bars = self._validate_bars(bars)

        self._process_order_block(
            bars=validated_bars,
            break_event=break_event,
            liquidity_event=liquidity_event,
        )
        self._process_fair_value_gap(validated_bars)

        order_block = self._latest_order_block(validated_bars)
        fair_value_gap = self._latest_fair_value_gap(validated_bars)
        confidence = self._confidence(
            order_block=order_block,
            fair_value_gap=fair_value_gap,
            bars=validated_bars,
        )

        return PriceActionResult(
            timestamp=validated_bars[-1].timestamp,
            last_order_block=order_block,
            last_fair_value_gap=fair_value_gap,
            price_action_confidence=confidence,
        )

    def _process_order_block(
        self,
        *,
        bars: list[MarketBar],
        break_event: BOSEvent | CHOCHEvent | None,
        liquidity_event: LiquiditySweepEvent | None,
    ) -> None:
        if break_event is None:
            return

        key = self._break_key(break_event)
        if key in self._processed_break_keys:
            return

        self.order_block_detector.process(
            break_event=break_event,
            bars=bars,
            liquidity_event=liquidity_event,
        )
        self._processed_break_keys.add(key)

    def _process_fair_value_gap(self, bars: list[MarketBar]) -> None:
        if len(bars) < 3:
            return

        window_key = tuple(bar.timestamp for bar in bars[-3:])
        if window_key in self._processed_fvg_windows:
            return

        update = getattr(
            self.fair_value_gap_detector,
            "update",
            None,
        )
        if callable(update):
            update(latest_bar=bars[-1])

        self.fair_value_gap_detector.process(bars)
        self._processed_fvg_windows.add(window_key)

    def _latest_order_block(self, bars: Sequence[MarketBar]) -> OrderBlock | None:
        getter = getattr(self.order_block_detector, "get_active_order_blocks", None)
        active = list(getter()) if callable(getter) else []

        if not active:
            getter = getattr(self.order_block_detector, "get_order_blocks", None)
            active = list(getter()) if callable(getter) else []

        usable = [
            block
            for block in active
            if self._evidence_age(block.timestamp, bars)
            <= self.maximum_evidence_age_bars
        ]
        if not usable:
            return None

        return max(
            usable,
            key=lambda block: (
                getattr(block, "confirmation_index", -1),
                block.timestamp,
            ),
        )

    def _latest_fair_value_gap(
        self,
        bars: Sequence[MarketBar],
    ) -> FairValueGap | FairValueGapCandidate | None:
        state = self.fair_value_gap_detector.state

        candidates: list[FairValueGap | FairValueGapCandidate] = []
        candidates.extend(getattr(state, "active_gaps", ()))
        candidates.extend(
            gap
            for gap in getattr(state, "confirmed_gaps", ())
            if self._is_usable_fvg(gap)
        )
        candidates.extend(
            gap
            for gap in getattr(state, "pending_candidates", ())
            if self._is_usable_fvg(gap)
        )

        last_gap = getattr(state, "last_gap", None)
        if last_gap is not None and self._is_usable_fvg(last_gap):
            candidates.append(last_gap)

        usable = [
            gap
            for gap in self._deduplicate_by_identity(candidates)
            if self._evidence_age(gap.timestamp, bars)
            <= self.maximum_evidence_age_bars
        ]
        if not usable:
            return None

        return max(
            usable,
            key=lambda gap: (
                gap.timestamp,
                getattr(getattr(gap, "third_bar", None), "timestamp", gap.timestamp),
                getattr(gap, "id", -1),
            ),
        )

    def _confidence(
        self,
        *,
        order_block: OrderBlock | None,
        fair_value_gap: FairValueGap | FairValueGapCandidate | None,
        bars: Sequence[MarketBar],
    ) -> float:
        weighted_scores: list[tuple[float, float]] = []

        if order_block is not None:
            weighted_scores.append(
                (
                    self._order_block_score(order_block, bars),
                    self._ORDER_BLOCK_WEIGHT,
                )
            )

        if fair_value_gap is not None:
            weighted_scores.append(
                (
                    self._fair_value_gap_score(fair_value_gap, bars),
                    self._FAIR_VALUE_GAP_WEIGHT,
                )
            )

        if not weighted_scores:
            return 0.0

        total_weight = sum(weight for _, weight in weighted_scores)
        confidence = sum(score * weight for score, weight in weighted_scores) / total_weight

        if (
            order_block is not None
            and fair_value_gap is not None
            and self._direction_name(order_block.block_type)
            != self._direction_name(fair_value_gap.gap_type)
        ):
            confidence *= self._CONFLICT_MULTIPLIER

        return self._bounded(confidence)

    def _order_block_score(
        self,
        order_block: OrderBlock,
        bars: Sequence[MarketBar],
    ) -> float:
        components: list[float] = []

        event = self._matching_order_block_event(order_block)
        if event is not None:
            components.append(self._bounded(event.analysis.total_score))

        break_quality = getattr(order_block.trigger_break, "quality", None)
        if break_quality is not None:
            components.append(self._bounded(float(break_quality)))

        liquidity = order_block.trigger_liquidity
        if liquidity is not None:
            liquidity_quality = getattr(liquidity, "quality", None)
            if liquidity_quality is not None:
                components.append(self._bounded(float(liquidity_quality)))

        base_quality = sum(components) / len(components) if components else 0.0
        return self._bounded(
            base_quality * self._freshness(order_block.timestamp, bars)
        )

    def _fair_value_gap_score(
        self,
        fair_value_gap: FairValueGap | FairValueGapCandidate,
        bars: Sequence[MarketBar],
    ) -> float:
        quality = float(getattr(fair_value_gap, "quality_score", 0.0))
        if not isfinite(quality):
            raise ValueError("Fair Value Gap quality_score must be finite")

        # The current FVG detector stores quality on a 0..100 scale.
        normalized_quality = quality / 100.0 if quality > 1.0 else quality
        return self._bounded(
            self._bounded(normalized_quality)
            * self._freshness(fair_value_gap.timestamp, bars)
        )

    def _matching_order_block_event(
        self,
        order_block: OrderBlock,
    ) -> OrderBlockEvent | None:
        getter = getattr(self.order_block_detector, "get_last_event", None)
        last_event = getter() if callable(getter) else None
        if last_event is not None and last_event.order_block == order_block:
            return last_event

        state = getattr(self.order_block_detector, "state", None)
        events = getattr(state, "confirmed_events", ())
        matching = [event for event in events if event.order_block == order_block]
        if not matching:
            return None
        return max(matching, key=lambda event: (event.confirmation_index, event.timestamp))

    def _freshness(
        self,
        timestamp: datetime,
        bars: Sequence[MarketBar],
    ) -> float:
        age = self._evidence_age(timestamp, bars)
        if age > self.maximum_evidence_age_bars:
            return 0.0
        return 0.5 ** (age / self.freshness_half_life_bars)

    @staticmethod
    def _evidence_age(timestamp: datetime, bars: Sequence[MarketBar]) -> int:
        for index in range(len(bars) - 1, -1, -1):
            if bars[index].timestamp <= timestamp:
                return len(bars) - 1 - index
        return len(bars)

    @staticmethod
    def _is_usable_fvg(gap: Any) -> bool:
        status = getattr(gap, "status", None)
        if status is None:
            return True
        status_name = str(getattr(status, "name", status)).upper()
        return status_name not in {"MITIGATED", "INVALIDATED", "ARCHIVED"}

    @staticmethod
    def _deduplicate_by_identity(values: Sequence[Any]) -> list[Any]:
        seen: set[int] = set()
        unique: list[Any] = []
        for value in values:
            identity = id(value)
            if identity in seen:
                continue
            seen.add(identity)
            unique.append(value)
        return unique

    @staticmethod
    def _direction_name(value: Any) -> str:
        name = getattr(value, "name", None)
        if name is None:
            name = getattr(value, "value", value)
        normalized = str(name).upper()
        if "BULL" in normalized:
            return "BULLISH"
        if "BEAR" in normalized:
            return "BEARISH"
        return "NEUTRAL"

    @staticmethod
    def _break_key(event: BOSEvent | CHOCHEvent) -> tuple[Any, ...]:
        return (
            event.break_type,
            event.direction,
            event.confirmation_index,
            event.timestamp,
            event.swing_point.timestamp,
            event.swing_point.price,
        )

    @staticmethod
    def _validate_bars(bars: Sequence[MarketBar]) -> list[MarketBar]:
        if isinstance(bars, (str, bytes)) or not isinstance(bars, Sequence):
            raise TypeError("bars must be a sequence of completed MarketBar objects")
        if not bars:
            raise ValueError("bars must not be empty")

        validated = list(bars)
        previous_timestamp: datetime | None = None

        for index, bar in enumerate(validated):
            if not isinstance(bar, MarketBar):
                raise TypeError(f"bars[{index}] must be a MarketBar")
            timestamp = bar.timestamp
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError(f"bars[{index}].timestamp must be timezone-aware")
            if previous_timestamp is not None and timestamp <= previous_timestamp:
                raise ValueError("bar timestamps must be strictly increasing")
            previous_timestamp = timestamp

            prices = (bar.open, bar.high, bar.low, bar.close)
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(float(value))
                for value in prices
            ):
                raise ValueError(f"bars[{index}] contains a non-finite price")
            if bar.high < max(bar.open, bar.close) or bar.low > min(
                bar.open, bar.close
            ):
                raise ValueError(f"bars[{index}] contains malformed OHLC values")
            if bar.high < bar.low:
                raise ValueError(f"bars[{index}] high must be at least low")

        return validated

    @staticmethod
    def _validate_positive_integer(value: int, *, field_name: str) -> None:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{field_name} must be an integer")
        if value < 1:
            raise ValueError(f"{field_name} must be at least 1")

    @staticmethod
    def _bounded(value: float) -> float:
        if not isfinite(value):
            raise ValueError("confidence component must be finite")
        return max(0.0, min(1.0, float(value)))
