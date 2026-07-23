"""Streaming Break of Structure (BOS) detection.

Two interfaces are intentionally supported:

- ``process(swing)`` preserves the legacy swing-to-swing contract.
- ``process_bar(...)`` is the production path and confirms a BOS only when a
  completed candle breaks an eligible structural swing level.
"""

from __future__ import annotations

from core.data.models import MarketBar
from core.market_structure.bos_measurement import (
    BOSMeasurement,
    BOSMeasurementEngine,
)
from core.market_structure.config import BOSDetectorConfig
from core.market_structure.enums import (
    BreakType,
    DetectorStatus,
    MarketTrend,
    SwingType,
    TrendDirection,
)
from core.market_structure.models import BOSEvent, SwingPoint
from core.market_structure.state import BOSDetectorState


class BOSDetector:
    """Detect completed-candle continuation breaks of structure."""

    def __init__(self, config: BOSDetectorConfig | None = None) -> None:
        self.config = config or BOSDetectorConfig()
        self.state = BOSDetectorState()
        self.measurement_engine = BOSMeasurementEngine()

    def reset(self) -> None:
        self.state.reset()

    def process(self, swing: SwingPoint) -> BOSEvent | None:
        """Preserve the original confirmed-swing interface.

        This compatibility path is retained for existing callers and tests.
        New orchestration code should use :meth:`process_bar`.
        """

        self._add_swing(swing)
        if not self._has_enough_swings():
            return None

        bullish_event = self._detect_bullish_bos(swing)
        if bullish_event is not None:
            return bullish_event
        return self._detect_bearish_bos(swing)

    def process_bar(
        self,
        bar: MarketBar,
        *,
        bar_index: int,
        swing: SwingPoint | None = None,
        atr: float | None = None,
    ) -> BOSEvent | None:
        """Process one completed candle using executable BOS semantics.

        A new confirmed swing can be supplied with the same call. The detector
        only emits continuation BOS events: opposite-direction protected-swing
        breaks are reserved for the CHOCH detector.
        """

        if isinstance(bar_index, bool) or not isinstance(bar_index, int):
            raise TypeError("bar_index must be an int")
        if bar_index < 0:
            raise ValueError("bar_index must be >= 0")
        if atr is not None and atr <= 0.0:
            raise ValueError("atr must be > 0 when supplied")

        if swing is not None:
            self._add_swing(swing)

        if not self.state.confirmed_swings:
            return None

        if self.state.current_trend in {
            MarketTrend.UNKNOWN,
            MarketTrend.BULLISH,
        }:
            bullish = self._detect_completed_bar_break(
                bar=bar,
                bar_index=bar_index,
                direction=TrendDirection.BULLISH,
                level=self._latest_swing(SwingType.HIGH),
                atr=atr,
            )
            if bullish is not None:
                return bullish

        if self.state.current_trend in {
            MarketTrend.UNKNOWN,
            MarketTrend.BEARISH,
        }:
            return self._detect_completed_bar_break(
                bar=bar,
                bar_index=bar_index,
                direction=TrendDirection.BEARISH,
                level=self._latest_swing(SwingType.LOW),
                atr=atr,
            )

        return None

    def _add_swing(self, swing: SwingPoint) -> None:
        if self.state.confirmed_swings:
            latest = self.state.confirmed_swings[-1]
            if latest == swing:
                return
            if latest.swing_type is swing.swing_type:
                more_extreme = (
                    swing.price > latest.price
                    if swing.swing_type is SwingType.HIGH
                    else swing.price < latest.price
                )
                if more_extreme:
                    self.state.confirmed_swings[-1] = swing
                    if getattr(self.state, "protected_swing", None) == latest:
                        self.state.protected_swing = swing
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

    def _latest_swing(self, swing_type: SwingType) -> SwingPoint | None:
        for swing in reversed(self.state.confirmed_swings):
            if swing.swing_type is swing_type:
                return swing
        return None

    def _detect_completed_bar_break(
        self,
        *,
        bar: MarketBar,
        bar_index: int,
        direction: TrendDirection,
        level: SwingPoint | None,
        atr: float | None,
    ) -> BOSEvent | None:
        if level is None or bar_index < level.confirmation_index:
            return None

        required_distance = self.config.minimum_break_distance
        if self.config.minimum_break_atr_multiple > 0.0:
            if atr is None:
                return None
            required_distance = max(
                required_distance,
                atr * self.config.minimum_break_atr_multiple,
            )

        threshold_distance = required_distance + self.config.break_tolerance
        break_price = self._completed_bar_break_price(
            bar=bar,
            direction=direction,
            level_price=level.price,
            threshold_distance=threshold_distance,
        )
        if break_price is None:
            return None

        break_distance = abs(break_price - level.price)
        synthetic_break = SwingPoint(
            timestamp=bar.timestamp,
            index=bar_index,
            price=break_price,
            swing_type=(
                SwingType.HIGH
                if direction is TrendDirection.BULLISH
                else SwingType.LOW
            ),
            confirmation_index=bar_index,
            distance_from_previous=break_distance,
            atr_multiple=(break_distance / atr if atr is not None else 0.0),
            pivot_dominance=level.pivot_dominance,
            confirmation_strength=1.0,
        )
        measurement = self.measurement_engine.evaluate(
            current_swing=synthetic_break,
            previous_swing=level,
        )

        event = BOSEvent(
            timestamp=bar.timestamp,
            break_type=BreakType.BOS,
            direction=direction,
            swing_point=level,
            break_price=break_price,
            confirmation_index=bar_index,
            break_distance=measurement.break_distance,
            break_atr_multiple=(
                measurement.break_distance / atr
                if atr is not None
                else 0.0
            ),
            strength=measurement.strength,
            quality=measurement.quality,
            power_score=measurement.power_score,
            structure_score=measurement.structure_score,
            age=0,
        )
        return self._store_event(event)

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

    # ------------------------------------------------------------------
    # Legacy swing-to-swing path
    # ------------------------------------------------------------------
    def _detect_bullish_bos(self, swing: SwingPoint) -> BOSEvent | None:
        if swing.swing_type is not SwingType.HIGH:
            return None
        previous_high = self._get_previous_same_type(swing)
        if previous_high is None:
            return None
        required_break = previous_high.price + self.config.minimum_break_distance
        if swing.price <= required_break:
            return None
        measurement = self.measurement_engine.evaluate(
            current_swing=swing,
            previous_swing=previous_high,
        )
        return self._create_legacy_bos_event(swing=swing, measurement=measurement)

    def _detect_bearish_bos(self, swing: SwingPoint) -> BOSEvent | None:
        if swing.swing_type is not SwingType.LOW:
            return None
        previous_low = self._get_previous_same_type(swing)
        if previous_low is None:
            return None
        required_break = previous_low.price - self.config.minimum_break_distance
        if swing.price >= required_break:
            return None
        measurement = self.measurement_engine.evaluate(
            current_swing=swing,
            previous_swing=previous_low,
        )
        return self._create_legacy_bos_event(swing=swing, measurement=measurement)

    def _create_legacy_bos_event(
        self,
        *,
        swing: SwingPoint,
        measurement: BOSMeasurement,
    ) -> BOSEvent | None:
        direction = (
            TrendDirection.BULLISH
            if swing.swing_type is SwingType.HIGH
            else TrendDirection.BEARISH
        )
        event = BOSEvent(
            timestamp=swing.timestamp,
            break_type=BreakType.BOS,
            direction=direction,
            break_price=swing.price,
            swing_point=swing,
            confirmation_index=swing.confirmation_index,
            break_distance=measurement.break_distance,
            break_atr_multiple=swing.atr_multiple,
            strength=measurement.strength,
            quality=measurement.quality,
            power_score=measurement.power_score,
            structure_score=measurement.structure_score,
            age=0,
        )
        return self._store_event(event)

    def _create_bos_event(
        self,
        *,
        swing: SwingPoint,
        measurement: BOSMeasurement,
    ) -> BOSEvent | None:
        """Backward-compatible alias for legacy private callers."""

        return self._create_legacy_bos_event(
            swing=swing,
            measurement=measurement,
        )

    def _store_event(self, event: BOSEvent) -> BOSEvent | None:
        if not self._validate_break(event):
            return None
        self.state.confirmed_breaks.append(event)
        self.state.last_break = event
        self._update_market_structure_state(event)
        self.state.detector_status = DetectorStatus.BREAK_CONFIRMED
        return event

    def _update_market_structure_state(self, event: BOSEvent) -> None:
        if event.direction is TrendDirection.BULLISH:
            self.state.current_trend = MarketTrend.BULLISH
            self.state.protected_swing = self._latest_swing_before(
                SwingType.LOW,
                event.confirmation_index,
            )
        else:
            self.state.current_trend = MarketTrend.BEARISH
            self.state.protected_swing = self._latest_swing_before(
                SwingType.HIGH,
                event.confirmation_index,
            )

    def _latest_swing_before(
        self,
        swing_type: SwingType,
        confirmation_index: int,
    ) -> SwingPoint | None:
        for swing in reversed(self.state.confirmed_swings):
            if (
                swing.swing_type is swing_type
                and swing.confirmation_index <= confirmation_index
            ):
                return swing
        return None

    def _find_last_swing(self, swing_type: SwingType) -> SwingPoint | None:
        """Preserve legacy private helper semantics."""

        for swing in reversed(self.state.confirmed_swings[:-1]):
            if swing.swing_type is swing_type:
                return swing
        return None

    def _validate_break(self, event: BOSEvent) -> bool:
        for previous in self.state.confirmed_breaks:
            if (
                previous.break_type is event.break_type
                and previous.swing_point == event.swing_point
                and previous.direction is event.direction
            ):
                return False
        return True

    @property
    def confirmed_break_count(self) -> int:
        return len(self.state.confirmed_breaks)

    def get_last_break(self) -> BOSEvent | None:
        return self.state.last_break

    def get_breaks(self) -> list[BOSEvent]:
        return list(self.state.confirmed_breaks)

    def get_state(self) -> BOSDetectorState:
        return self.state
