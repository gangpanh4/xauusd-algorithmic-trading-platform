"""Market Structure Engine.

Coordinates streaming swing, BOS, CHOCH, and liquidity detectors while owning
bar-based event freshness and expiry. Detection remains inside the individual
detectors; this engine only orchestrates dependencies and lifecycle state.
"""

from __future__ import annotations

from collections import deque
from dataclasses import replace
from typing import TypeVar

from core.data.models import MarketBar
from core.market_structure.bos_detector import BOSDetector
from core.market_structure.choch_detector import CHOCHDetector
from core.market_structure.config import (
    MarketStructureConfig,
    SwingDetectorConfig,
)
from core.market_structure.liquidity_detector import LiquidityDetector
from core.market_structure.measurement_engine import MeasurementEngine
from core.market_structure.enums import SwingType
from core.market_structure.models import (
    BOSEvent,
    CHOCHEvent,
    LiquiditySweepEvent,
    MarketStructureResult,
    StructureState,
    SwingPoint,
)
from core.market_structure.swing_detector import SwingDetector
from core.market_structure.swing_evaluator import StructureEvaluator


_EventT = TypeVar(
    "_EventT",
    BOSEvent,
    CHOCHEvent,
    LiquiditySweepEvent,
)


class MarketStructureEngine:
    """High-level streaming market-structure orchestrator."""

    def __init__(
        self,
        config: MarketStructureConfig | SwingDetectorConfig | None = None,
    ) -> None:
        if config is None:
            resolved_config = MarketStructureConfig()
        elif isinstance(config, MarketStructureConfig):
            resolved_config = config
        elif isinstance(config, SwingDetectorConfig):
            # Backward compatibility with the former alias-based public API.
            resolved_config = MarketStructureConfig(swing=config)
        else:
            raise TypeError(
                "config must be MarketStructureConfig, "
                "SwingDetectorConfig, or None"
            )

        self.config = resolved_config
        self.bar_history: deque[MarketBar] = deque(
            maxlen=self.config.maximum_bar_history
        )
        self.swing_detector = SwingDetector(self.config.swing)
        self.bos_detector = BOSDetector(self.config.bos)
        self.choch_detector = CHOCHDetector(
            config=self.config.choch,
            bos_state=self.bos_detector.state,
        )
        self.liquidity_detector = LiquidityDetector(self.config.liquidity)
        self.measurement_engine = MeasurementEngine()
        self.structure_evaluator = StructureEvaluator(
            freshness_decay_bars=self.config.freshness_decay_bars,
            swing_weight=self.config.swing_confidence_weight,
            bos_weight=self.config.bos_confidence_weight,
            choch_weight=self.config.choch_confidence_weight,
            liquidity_weight=self.config.liquidity_confidence_weight,
        )

    def reset(self) -> None:
        """Reset all detector and orchestration state."""

        self.swing_detector.reset()
        self.bos_detector.reset()
        self.choch_detector.reset()
        self.liquidity_detector.reset()
        self.bar_history.clear()

    def process(self, bar: MarketBar) -> MarketStructureResult:
        """Process one completed market bar."""

        self.bar_history.append(bar)
        swing = self.swing_detector.process(bar)

        current_bar_index = self.swing_detector.state.processed_bar_count - 1
        atr = self._calculate_atr()

        # Every completed candle can confirm a structural break or sweep.
        # A newly confirmed swing is registered with all three detectors in
        # the same call, but detection is never limited to swing bars.
        self.bos_detector.process_bar(
            bar,
            bar_index=current_bar_index,
            swing=swing,
            atr=atr,
        )
        self.choch_detector.process_bar(
            bar,
            bar_index=current_bar_index,
            swing=swing,
            atr=atr,
        )
        self.liquidity_detector.process_bar(
            bar,
            bar_index=current_bar_index,
            swing=swing,
            atr=atr,
        )

        self._refresh_event_lifecycle(current_bar_index)

        last_bos = self.bos_detector.get_last_break()
        last_choch = self.choch_detector.state.last_change
        last_liquidity = self.liquidity_detector.get_last_sweep()
        last_swing = self.swing_detector.get_last_swing()

        measurements = self.measurement_engine.calculate(
            current_bar=bar,
            last_bos=last_bos,
            last_choch=last_choch,
            last_liquidity=last_liquidity,
            last_swing=last_swing,
        )

        # MeasurementEngine cannot infer completed-bar distance from timestamps
        # alone. The streaming engine owns the authoritative bar indexes.
        measurements.bos_age = last_bos.age if last_bos is not None else 0
        measurements.choch_age = (
            last_choch.age if last_choch is not None else 0
        )
        measurements.liquidity_age = (
            last_liquidity.age if last_liquidity is not None else 0
        )
        measurements.swing_age = (
            max(0, current_bar_index - last_swing.confirmation_index)
            if last_swing is not None
            else 0
        )

        evaluation = self.structure_evaluator.evaluate(
            swing=last_swing,
            bos=last_bos,
            choch=last_choch,
            liquidity=last_liquidity,
        )

        structure_state = self._build_structure_state(
            timestamp=bar.timestamp,
            current_bar_index=current_bar_index,
            last_bos=last_bos,
            last_choch=last_choch,
            last_liquidity=last_liquidity,
        )

        return MarketStructureResult(
            timestamp=bar.timestamp,
            last_swing=last_swing,
            last_bos=last_bos,
            last_choch=last_choch,
            last_liquidity=last_liquidity,
            current_trend=self.bos_detector.state.current_trend,
            structure_confidence=evaluation.confidence,
            swing_score=evaluation.swing_score,
            bos_score=evaluation.bos_score,
            choch_score=evaluation.choch_score,
            liquidity_score=evaluation.liquidity_score,
            bos_freshness=evaluation.bos_freshness,
            choch_freshness=evaluation.choch_freshness,
            liquidity_freshness=evaluation.liquidity_freshness,
            freshness_decay_bars=self.config.freshness_decay_bars,
            measurements=measurements,
            structure_state=structure_state,
        )

    def _build_structure_state(
        self,
        *,
        timestamp,
        current_bar_index: int,
        last_bos: BOSEvent | None,
        last_choch: CHOCHEvent | None,
        last_liquidity: LiquiditySweepEvent | None,
    ) -> StructureState:
        """Build one immutable snapshot from authoritative detector state."""

        swings = self.swing_detector.get_swings()
        last_high = self._latest_swing_of_type(swings, SwingType.HIGH)
        last_low = self._latest_swing_of_type(swings, SwingType.LOW)

        protected = self.bos_detector.state.protected_swing
        protected_high = (
            protected
            if protected is not None
            and protected.swing_type is SwingType.HIGH
            else None
        )
        protected_low = (
            protected
            if protected is not None
            and protected.swing_type is SwingType.LOW
            else None
        )

        return StructureState(
            timestamp=timestamp,
            current_bar_index=current_bar_index,
            trend=self.bos_detector.state.current_trend,
            confirmed_swings=swings,
            last_swing=(swings[-1] if swings else None),
            last_high=last_high,
            last_low=last_low,
            protected_high=protected_high,
            protected_low=protected_low,
            last_bos=last_bos,
            last_choch=last_choch,
            last_liquidity=last_liquidity,
            tracked_liquidity_levels=tuple(
                self.liquidity_detector.state.liquidity_levels
            ),
        )

    @staticmethod
    def _latest_swing_of_type(
        swings: tuple[SwingPoint, ...],
        swing_type: SwingType,
    ) -> SwingPoint | None:
        for swing in reversed(swings):
            if swing.swing_type is swing_type:
                return swing
        return None

    def _calculate_atr(self) -> float | None:
        """Return a simple streaming ATR from completed bar history.

        A full ATR period plus the preceding close is required. This avoids
        silently using an unstable partial-period volatility estimate for
        configured ATR thresholds.
        """

        period = self.config.swing.atr_period
        if len(self.bar_history) < period + 1:
            return None

        bars = list(self.bar_history)[-(period + 1) :]
        true_ranges: list[float] = []
        for previous, current in zip(bars, bars[1:]):
            true_ranges.append(
                max(
                    current.high - current.low,
                    abs(current.high - previous.close),
                    abs(current.low - previous.close),
                )
            )

        if not true_ranges:
            return None

        atr = sum(true_ranges) / len(true_ranges)
        return atr if atr > 0.0 else None

    def _refresh_event_lifecycle(self, current_bar_index: int) -> None:
        """Age current events and expire evidence beyond configured limits."""

        last_bos = self._aged_event(
            self.bos_detector.state.last_break,
            current_bar_index=current_bar_index,
            maximum_age=self.config.maximum_bos_age_bars,
        )
        self.bos_detector.state.last_break = last_bos
        self._replace_latest_history_event(
            self.bos_detector.state.confirmed_breaks,
            last_bos,
        )

        last_choch = self._aged_event(
            self.choch_detector.state.last_change,
            current_bar_index=current_bar_index,
            maximum_age=self.config.maximum_choch_age_bars,
        )
        self.choch_detector.state.last_change = last_choch
        self._replace_latest_history_event(
            self.choch_detector.state.confirmed_changes,
            last_choch,
        )

        last_liquidity = self._aged_event(
            self.liquidity_detector.state.last_sweep,
            current_bar_index=current_bar_index,
            maximum_age=self.config.maximum_liquidity_age_bars,
        )
        self.liquidity_detector.state.last_sweep = last_liquidity
        self._replace_latest_history_event(
            self.liquidity_detector.state.confirmed_sweeps,
            last_liquidity,
        )

    def _aged_event(
        self,
        event: _EventT | None,
        *,
        current_bar_index: int,
        maximum_age: int,
    ) -> _EventT | None:
        if event is None:
            return None

        age = max(0, current_bar_index - event.confirmation_index)
        if self.config.expire_stale_events and age > maximum_age:
            return None

        if event.age == age:
            return event

        return replace(event, age=age)

    @staticmethod
    def _replace_latest_history_event(
        history: list[_EventT],
        event: _EventT | None,
    ) -> None:
        """Keep the latest retained history object consistent with state."""

        if event is None or not history:
            return

        latest = history[-1]
        if latest.confirmation_index == event.confirmation_index:
            history[-1] = event

    def get_bar_history(self) -> tuple[MarketBar, ...]:
        """Return immutable historical market bars, oldest to newest."""

        return tuple(self.bar_history)

    def get_latest_bar(self) -> MarketBar | None:
        """Return the latest completed market bar."""

        if not self.bar_history:
            return None
        return self.bar_history[-1]
