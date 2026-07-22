"""Streaming Change of Character (CHOCH) detection.

``process(swing)`` preserves the legacy swing-to-swing contract.
``process_bar(...)`` is the production path and confirms a reversal only when a
completed candle breaks the active BOS protected swing.
"""

from __future__ import annotations

from core.data.models import MarketBar
from core.market_structure.choch_measurement import CHOCHMeasurementEngine
from core.market_structure.config import CHOCHDetectorConfig
from core.market_structure.enums import (
    BreakType,
    DetectorStatus,
    MarketTrend,
    SwingType,
    TrendDirection,
)
from core.market_structure.models import CHOCHEvent, SwingPoint
from core.market_structure.state import BOSDetectorState, CHOCHDetectorState


class CHOCHDetector:
    """Detect completed-candle breaks against the protected swing."""

    def __init__(
        self,
        bos_state: BOSDetectorState,
        config: CHOCHDetectorConfig | None = None,
    ) -> None:
        self.config = config or CHOCHDetectorConfig()
        self.bos_state = bos_state
        self.state = CHOCHDetectorState()
        self.measurement_engine = CHOCHMeasurementEngine()

    def reset(self) -> None:
        self.state.reset()

    def process(self, swing: SwingPoint) -> CHOCHEvent | None:
        """Preserve the original confirmed-swing interface."""

        self._add_swing(swing)
        bearish_event = self._detect_bearish_choch(swing)
        if bearish_event is not None:
            return bearish_event
        return self._detect_bullish_choch(swing)

    def process_bar(
        self,
        bar: MarketBar,
        *,
        bar_index: int,
        swing: SwingPoint | None = None,
        atr: float | None = None,
    ) -> CHOCHEvent | None:
        """Process one completed candle against the protected swing."""

        if isinstance(bar_index, bool) or not isinstance(bar_index, int):
            raise TypeError("bar_index must be an int")
        if bar_index < 0:
            raise ValueError("bar_index must be >= 0")
        if atr is not None and atr <= 0.0:
            raise ValueError("atr must be > 0 when supplied")

        if swing is not None:
            self._add_swing(swing)

        protected = self._get_protected_swing()
        trend = self._get_current_trend()
        if protected is None or trend is MarketTrend.UNKNOWN:
            return None
        if bar_index < protected.confirmation_index:
            return None

        if trend is MarketTrend.BULLISH:
            direction = TrendDirection.BEARISH
        elif trend is MarketTrend.BEARISH:
            direction = TrendDirection.BULLISH
        else:
            return None

        required_distance = self.config.minimum_break_distance
        if self.config.minimum_break_atr_multiple > 0.0:
            if atr is None:
                return None
            required_distance = max(
                required_distance,
                atr * self.config.minimum_break_atr_multiple,
            )

        break_price = self._completed_bar_break_price(
            bar=bar,
            direction=direction,
            level_price=protected.price,
            threshold_distance=required_distance,
        )
        if break_price is None:
            return None

        break_distance = abs(break_price - protected.price)
        event = self._build_event(
            timestamp=bar.timestamp,
            direction=direction,
            break_price=break_price,
            broken_swing=protected,
            confirmation_index=bar_index,
            break_distance=break_distance,
            break_atr_multiple=(
                break_distance / atr if atr is not None else 0.0
            ),
        )
        stored = self._store_event(event)
        if stored is None:
            return None

        self._apply_trend_change(stored)
        return stored

    def _completed_bar_break_price(
        self,
        *,
        bar: MarketBar,
        direction: TrendDirection,
        level_price: float,
        threshold_distance: float,
    ) -> float | None:
        if direction is TrendDirection.BULLISH:
            threshold = level_price + threshold_distance
            if self.config.require_close_break and bar.close > threshold:
                return bar.close
            if self.config.allow_wick_break and bar.high > threshold:
                return bar.high
            return None

        threshold = level_price - threshold_distance
        if self.config.require_close_break and bar.close < threshold:
            return bar.close
        if self.config.allow_wick_break and bar.low < threshold:
            return bar.low
        return None

    def _add_swing(self, swing: SwingPoint) -> None:
        if self.state.confirmed_swings and self.state.confirmed_swings[-1] == swing:
            return
        self.state.confirmed_swings.append(swing)
        self.state.processed_swing_count += 1
        self.state.detector_status = DetectorStatus.RUNNING

        overflow = len(self.state.confirmed_swings) - self.config.maximum_history
        if overflow > 0:
            del self.state.confirmed_swings[:overflow]

    def _has_enough_swings(self) -> bool:
        return len(self.state.confirmed_swings) >= 2

    def _get_previous_same_type(self, swing: SwingPoint) -> SwingPoint | None:
        if len(self.state.confirmed_swings) < 2:
            return None
        for previous in reversed(self.state.confirmed_swings[:-1]):
            if previous.swing_type is swing.swing_type:
                return previous
        return None

    def _get_current_trend(self) -> MarketTrend:
        return self.bos_state.current_trend

    def _get_protected_swing(self) -> SwingPoint | None:
        return self.bos_state.protected_swing

    @staticmethod
    def _calculate_break_distance(
        current: SwingPoint,
        protected: SwingPoint,
    ) -> float:
        return abs(current.price - protected.price)

    # ------------------------------------------------------------------
    # Legacy swing-to-swing path
    # ------------------------------------------------------------------
    def _detect_bearish_choch(self, swing: SwingPoint) -> CHOCHEvent | None:
        if self._get_current_trend() is not MarketTrend.BULLISH:
            return None
        if swing.swing_type is not SwingType.LOW:
            return None
        protected = self._get_protected_swing()
        if protected is None:
            return None
        required = protected.price - self.config.minimum_break_distance
        if swing.price >= required:
            return None
        return self._create_choch_event(
            swing=swing,
            break_type=BreakType.CHOCH,
            break_distance=self._calculate_break_distance(swing, protected),
        )

    def _detect_bullish_choch(self, swing: SwingPoint) -> CHOCHEvent | None:
        if self._get_current_trend() is not MarketTrend.BEARISH:
            return None
        if swing.swing_type is not SwingType.HIGH:
            return None
        protected = self._get_protected_swing()
        if protected is None:
            return None
        required = protected.price + self.config.minimum_break_distance
        if swing.price <= required:
            return None
        return self._create_choch_event(
            swing=swing,
            break_type=BreakType.CHOCH,
            break_distance=self._calculate_break_distance(swing, protected),
        )

    def _create_choch_event(
        self,
        *,
        swing: SwingPoint,
        break_type: BreakType,
        break_distance: float,
    ) -> CHOCHEvent | None:
        direction = (
            TrendDirection.BULLISH
            if swing.swing_type is SwingType.HIGH
            else TrendDirection.BEARISH
        )
        event = self._build_event(
            timestamp=swing.timestamp,
            direction=direction,
            break_price=swing.price,
            broken_swing=swing,
            confirmation_index=swing.confirmation_index,
            break_distance=break_distance,
            break_atr_multiple=swing.atr_multiple,
            break_type=break_type,
        )
        return self._store_event(event)

    def _build_event(
        self,
        *,
        timestamp,
        direction: TrendDirection,
        break_price: float,
        broken_swing: SwingPoint,
        confirmation_index: int,
        break_distance: float,
        break_atr_multiple: float = 0.0,
        break_type: BreakType = BreakType.CHOCH,
    ) -> CHOCHEvent:
        raw_event = CHOCHEvent(
            timestamp=timestamp,
            break_type=break_type,
            direction=direction,
            break_price=break_price,
            swing_point=broken_swing,
            confirmation_index=confirmation_index,
            break_distance=break_distance,
            break_atr_multiple=break_atr_multiple,
        )
        measurement = self.measurement_engine.evaluate(raw_event)
        return CHOCHEvent(
            timestamp=timestamp,
            break_type=break_type,
            direction=direction,
            break_price=break_price,
            swing_point=broken_swing,
            confirmation_index=confirmation_index,
            break_distance=measurement.break_distance,
            break_atr_multiple=break_atr_multiple,
            quality=measurement.quality,
            strength=measurement.strength,
            power_score=measurement.power_score,
            structure_score=measurement.structure_score,
            age=0,
        )

    def _store_event(self, event: CHOCHEvent) -> CHOCHEvent | None:
        if not self._validate_change(event):
            return None
        self.state.confirmed_changes.append(event)
        self.state.last_change = event
        self.state.detector_status = DetectorStatus.BREAK_CONFIRMED
        return event

    def _validate_change(self, event: CHOCHEvent) -> bool:
        for previous in self.state.confirmed_changes:
            if (
                previous.break_type is event.break_type
                and previous.swing_point == event.swing_point
                and previous.direction is event.direction
            ):
                return False
        return True

    def _apply_trend_change(self, event: CHOCHEvent) -> None:
        if not self.config.require_trend_change:
            return

        if event.direction is TrendDirection.BULLISH:
            self.bos_state.current_trend = MarketTrend.BULLISH
            self.bos_state.protected_swing = self._latest_swing(
                SwingType.LOW,
                before_or_at=event.confirmation_index,
            )
        else:
            self.bos_state.current_trend = MarketTrend.BEARISH
            self.bos_state.protected_swing = self._latest_swing(
                SwingType.HIGH,
                before_or_at=event.confirmation_index,
            )

    def _latest_swing(
        self,
        swing_type: SwingType,
        *,
        before_or_at: int,
    ) -> SwingPoint | None:
        # BOS receives the same swing stream and may have more complete history.
        sources = (
            self.bos_state.confirmed_swings,
            self.state.confirmed_swings,
        )
        candidates = [
            swing
            for source in sources
            for swing in source
            if (
                swing.swing_type is swing_type
                and swing.confirmation_index <= before_or_at
            )
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda item: item.confirmation_index)

    # Backward-compatible private methods now operate on BOS-owned state.
    def _update_trend(self) -> None:
        last = self.state.last_change
        if last is not None:
            self._apply_trend_change(last)

    def _update_protected_swing(self, swing: SwingPoint) -> None:
        self.bos_state.protected_swing = swing

    def _is_bullish_trend(self) -> bool:
        return self.bos_state.current_trend is MarketTrend.BULLISH

    def _is_bearish_trend(self) -> bool:
        return self.bos_state.current_trend is MarketTrend.BEARISH

    @property
    def confirmed_change_count(self) -> int:
        return len(self.state.confirmed_changes)
