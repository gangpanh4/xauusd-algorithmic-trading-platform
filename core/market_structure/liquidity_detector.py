"""Streaming liquidity sweep-and-reclaim detection.

``process(swing)`` preserves the legacy swing-to-swing interface.
``process_bar(...)`` is the production path and requires actual candle
penetration of a confirmed level plus a reclaim close by default.
"""

from __future__ import annotations

import math
from datetime import datetime

from core.data.models import MarketBar
from core.market_structure.config import LiquidityDetectorConfig
from core.market_structure.enums import DetectorStatus, SwingType
from core.market_structure.models import (
    LiquidityLevel,
    LiquiditySweepEvent,
    SwingPoint,
)
from core.market_structure.state import LiquidityDetectorState


class LiquidityDetector:
    """Detect completed-candle liquidity sweeps and reclaims."""

    def __init__(
        self,
        config: LiquidityDetectorConfig | None = None,
    ) -> None:
        self.config = config or LiquidityDetectorConfig()
        self.state = LiquidityDetectorState()
        self._swept_level_keys: set[tuple[bool, datetime, int, str]] = set()
        self._indexed_sweep_count = 0

    def reset(self) -> None:
        self.state.reset()
        self._swept_level_keys.clear()
        self._indexed_sweep_count = 0

    def process(self, swing: SwingPoint) -> LiquiditySweepEvent | None:
        """Preserve the original confirmed-swing interface."""

        self._add_level(swing, replace_latest=False)
        buy_side = self._detect_buy_side_sweep(swing)
        if buy_side is not None:
            return buy_side
        return self._detect_sell_side_sweep(swing)

    def process_bar(
        self,
        bar: MarketBar,
        *,
        bar_index: int,
        swing: SwingPoint | None = None,
        atr: float | None = None,
    ) -> LiquiditySweepEvent | None:
        """Process one completed bar for sweep-and-reclaim evidence."""

        if isinstance(bar_index, bool) or not isinstance(bar_index, int):
            raise TypeError("bar_index must be an int")
        if bar_index < 0:
            raise ValueError("bar_index must be >= 0")
        if atr is not None and atr <= 0.0:
            raise ValueError("atr must be > 0 when supplied")

        if swing is not None:
            self._add_level(swing, replace_latest=True)

        buy_side = self._detect_completed_buy_side_sweep(
            bar=bar,
            bar_index=bar_index,
            atr=atr,
        )
        if buy_side is not None:
            return buy_side

        return self._detect_completed_sell_side_sweep(
            bar=bar,
            bar_index=bar_index,
            atr=atr,
        )

    def _add_level(
        self,
        swing: SwingPoint,
        *,
        replace_latest: bool = False,
    ) -> None:
        level = LiquidityLevel(
            timestamp=swing.timestamp,
            price=swing.price,
            swing_point=swing,
            is_buy_side=swing.swing_type is SwingType.HIGH,
        )

        if self.state.liquidity_levels:
            latest = self.state.liquidity_levels[-1]
            if latest.swing_point == swing:
                return
            if replace_latest and latest.is_buy_side == level.is_buy_side:
                more_extreme = (
                    level.price > latest.price
                    if level.is_buy_side
                    else level.price < latest.price
                )
                equal_price = level.price == latest.price

                if more_extreme:
                    self.state.liquidity_levels[-1] = level
                    return

                if equal_price:
                    if not self.config.allow_equal_levels:
                        return
                    # Equal-price pools from distinct confirmed swings remain
                    # independent liquidity facts. Fall through and append.
                else:
                    # A less-extreme consecutive level cannot replace the
                    # active structural candidate.
                    return

            if (
                not self.config.allow_equal_levels
                and latest.is_buy_side == level.is_buy_side
                and latest.price == level.price
            ):
                return

        self.state.liquidity_levels.append(level)
        self.state.processed_swing_count += 1

        overflow = len(self.state.liquidity_levels) - self.config.maximum_history
        if overflow > 0:
            del self.state.liquidity_levels[:overflow]

    def get_last_sweep(self) -> LiquiditySweepEvent | None:
        return self.state.last_sweep

    def _detect_completed_buy_side_sweep(
        self,
        *,
        bar: MarketBar,
        bar_index: int,
        atr: float | None,
    ) -> LiquiditySweepEvent | None:
        for level in reversed(self.state.liquidity_levels):
            if not level.is_buy_side:
                continue
            if bar_index <= level.swing_point.confirmation_index:
                continue
            if self._level_already_swept(level):
                continue

            required_distance = self._required_sweep_distance(atr)
            if bar.high <= level.price + required_distance:
                continue
            if self.config.require_reclaim_close and bar.close >= level.price:
                continue

            return self._create_completed_sweep_event(
                level=level,
                timestamp=bar.timestamp,
                sweep_price=bar.high,
                reclaim_close=bar.close,
                confirmation_index=bar_index,
                atr=atr,
            )
        return None

    def _detect_completed_sell_side_sweep(
        self,
        *,
        bar: MarketBar,
        bar_index: int,
        atr: float | None,
    ) -> LiquiditySweepEvent | None:
        for level in reversed(self.state.liquidity_levels):
            if level.is_buy_side:
                continue
            if bar_index <= level.swing_point.confirmation_index:
                continue
            if self._level_already_swept(level):
                continue

            required_distance = self._required_sweep_distance(atr)
            if bar.low >= level.price - required_distance:
                continue
            if self.config.require_reclaim_close and bar.close <= level.price:
                continue

            return self._create_completed_sweep_event(
                level=level,
                timestamp=bar.timestamp,
                sweep_price=bar.low,
                reclaim_close=bar.close,
                confirmation_index=bar_index,
                atr=atr,
            )
        return None

    def _required_sweep_distance(self, atr: float | None) -> float:
        required = self.config.minimum_sweep_distance
        if self.config.minimum_sweep_atr_multiple > 0.0:
            if atr is None:
                return math.inf
            required = max(
                required,
                atr * self.config.minimum_sweep_atr_multiple,
            )
        return required

    def _level_already_swept(self, level: LiquidityLevel) -> bool:
        self._synchronize_sweep_index()
        return self._level_key(level) in self._swept_level_keys

    @staticmethod
    def _level_key(
        level: LiquidityLevel,
    ) -> tuple[bool, datetime, int, str]:
        """Return the stable identity of one confirmed liquidity pool.

        The key is based on the originating swing fact rather than direct
        floating-point equality. Two equal-price pools confirmed at different
        swings remain independent market facts.
        """

        swing = level.swing_point
        return (
            level.is_buy_side,
            swing.timestamp,
            swing.confirmation_index,
            float(level.price).hex(),
        )

    def _synchronize_sweep_index(self) -> None:
        """Rebuild the private index only after external state mutation.

        Normal detector operation appends events through ``_store_event`` and
        therefore maintains O(1) membership checks. The public state object is
        retained for compatibility, so this guard repairs the index if a test
        or integration mutates ``confirmed_sweeps`` directly.
        """

        sweep_count = len(self.state.confirmed_sweeps)
        if sweep_count == self._indexed_sweep_count:
            return

        self._swept_level_keys = {
            self._level_key(event.liquidity_level)
            for event in self.state.confirmed_sweeps
        }
        self._indexed_sweep_count = sweep_count

    def _create_completed_sweep_event(
        self,
        *,
        level: LiquidityLevel,
        timestamp,
        sweep_price: float,
        reclaim_close: float,
        confirmation_index: int,
        atr: float | None,
    ) -> LiquiditySweepEvent | None:
        sweep_distance = self._calculate_sweep_distance(
            level=level,
            sweep_price=sweep_price,
        )
        scale = (
            atr
            if atr is not None
            else max(abs(level.price) * 0.0001, 1e-6)
        )
        sweep_strength = 1.0 - math.exp(-sweep_distance / scale)

        if level.is_buy_side:
            reaction_distance = max(0.0, sweep_price - reclaim_close)
            reclaim_distance = max(0.0, level.price - reclaim_close)
        else:
            reaction_distance = max(0.0, reclaim_close - sweep_price)
            reclaim_distance = max(0.0, reclaim_close - level.price)

        reaction_strength = min(
            reaction_distance / max(sweep_distance, 1e-9),
            1.0,
        )
        reclaim_strength = min(
            reclaim_distance / max(sweep_distance, 1e-9),
            1.0,
        )
        density = self._calculate_density(level)
        atr_multiple = sweep_distance / atr if atr is not None else 0.0
        normalized_atr = min(atr_multiple / 3.0, 1.0)
        quality = (
            normalized_atr * 0.25
            + density * 0.15
            + sweep_strength * 0.20
            + reaction_strength * 0.20
            + reclaim_strength * 0.20
        )

        event = LiquiditySweepEvent(
            timestamp=timestamp,
            liquidity_level=level,
            sweep_price=sweep_price,
            confirmation_index=confirmation_index,
            sweep_distance=sweep_distance,
            atr_multiple=atr_multiple,
            sweep_strength=sweep_strength,
            reaction_strength=reaction_strength,
            reclaim_strength=reclaim_strength,
            density=density,
            quality=quality,
            age=0,
        )
        return self._store_event(event)

    # ------------------------------------------------------------------
    # Legacy swing-to-swing path
    # ------------------------------------------------------------------
    def _detect_buy_side_sweep(
        self,
        swing: SwingPoint,
    ) -> LiquiditySweepEvent | None:
        if swing.swing_type is not SwingType.HIGH:
            return None
        for level in reversed(self.state.liquidity_levels[:-1]):
            if not level.is_buy_side:
                continue
            required_break = level.price + self.config.minimum_sweep_distance
            if swing.price <= required_break:
                continue
            return self._create_sweep_event(
                level=level,
                sweep_price=swing.price,
                confirmation_index=swing.confirmation_index,
                sweep_distance=self._calculate_sweep_distance(
                    level=level,
                    sweep_price=swing.price,
                ),
            )
        return None

    def _detect_sell_side_sweep(
        self,
        swing: SwingPoint,
    ) -> LiquiditySweepEvent | None:
        if swing.swing_type is not SwingType.LOW:
            return None
        for level in reversed(self.state.liquidity_levels[:-1]):
            if level.is_buy_side:
                continue
            required_break = level.price - self.config.minimum_sweep_distance
            if swing.price >= required_break:
                continue
            return self._create_sweep_event(
                level=level,
                sweep_price=swing.price,
                confirmation_index=swing.confirmation_index,
                sweep_distance=self._calculate_sweep_distance(
                    level=level,
                    sweep_price=swing.price,
                ),
            )
        return None

    @staticmethod
    def _calculate_sweep_distance(
        *,
        level: LiquidityLevel,
        sweep_price: float,
    ) -> float:
        return abs(sweep_price - level.price)

    def _calculate_sweep_strength(self, sweep_distance: float) -> float:
        scale = max(
            self.config.minimum_sweep_distance * 10.0,
            1e-9,
        )
        return 1.0 - math.exp(-sweep_distance / scale)

    @staticmethod
    def _calculate_density(level: LiquidityLevel) -> float:
        return max(0.0, min(level.swing_point.pivot_dominance, 1.0))

    def _create_sweep_event(
        self,
        *,
        level: LiquidityLevel,
        sweep_price: float,
        confirmation_index: int,
        sweep_distance: float,
    ) -> LiquiditySweepEvent | None:
        sweep_strength = self._calculate_sweep_strength(sweep_distance)
        reaction_strength = 1.0 - math.exp(
            -sweep_distance
            / max(self.config.minimum_sweep_distance * 5.0, 1e-9)
        )
        reclaim_strength = min(
            sweep_distance / max(level.price, 1e-9),
            1.0,
        )
        density = self._calculate_density(level)
        atr_multiple = level.swing_point.atr_multiple
        normalized_atr = min(atr_multiple / 5.0, 1.0)
        quality = (
            normalized_atr * 0.35
            + density * 0.20
            + sweep_strength * 0.20
            + reaction_strength * 0.15
            + reclaim_strength * 0.10
        )
        event = LiquiditySweepEvent(
            timestamp=level.timestamp,
            liquidity_level=level,
            sweep_price=sweep_price,
            confirmation_index=confirmation_index,
            sweep_distance=sweep_distance,
            atr_multiple=atr_multiple,
            sweep_strength=sweep_strength,
            reaction_strength=reaction_strength,
            reclaim_strength=reclaim_strength,
            density=density,
            quality=quality,
        )
        return self._store_event(event)

    def _store_event(
        self,
        event: LiquiditySweepEvent,
    ) -> LiquiditySweepEvent | None:
        if not self._validate_sweep(event):
            return None
        self._synchronize_sweep_index()
        self.state.confirmed_sweeps.append(event)
        self._swept_level_keys.add(self._level_key(event.liquidity_level))
        self._indexed_sweep_count += 1
        self.state.last_sweep = event
        self.state.detector_status = DetectorStatus.BREAK_CONFIRMED
        return event

    def _validate_sweep(self, event: LiquiditySweepEvent) -> bool:
        return not self._level_already_swept(event.liquidity_level)

    @property
    def confirmed_sweep_count(self) -> int:
        return len(self.state.confirmed_sweeps)

    def get_sweeps(self) -> list[LiquiditySweepEvent]:
        return list(self.state.confirmed_sweeps)

    def get_state(self) -> LiquidityDetectorState:
        return self.state
