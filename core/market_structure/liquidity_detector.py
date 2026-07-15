"""
Streaming Liquidity Sweep Detection Engine.
"""

from __future__ import annotations

from core.market_structure.config import LiquidityDetectorConfig
from core.market_structure.models import (
    LiquidityLevel,
    LiquiditySweepEvent,
    SwingPoint,
)
from core.market_structure.state import LiquidityDetectorState
from core.market_structure.enums import DetectorStatus, SwingType
from core.regime_detector import detector
from tests.market_structure.test_bos_detector import make_swing


class LiquidityDetector:
    """
    Streaming Liquidity Sweep Detection Engine.

    The detector consumes confirmed SwingPoint objects and emits
    confirmed LiquiditySweepEvent objects whenever a valid
    liquidity sweep is detected.
    """

    def __init__(
        self,
        config: LiquidityDetectorConfig | None = None,
    ) -> None:
        """
        Initialize the Liquidity Sweep Detector.
        """

        self.config = config or LiquidityDetectorConfig()
        self.state = LiquidityDetectorState()

    def reset(self) -> None:
        """
        Reset the detector state.
        """

        self.state.reset()

    def process(
        self,
        swing: SwingPoint,
    ) -> LiquiditySweepEvent | None:
        """
        Process one confirmed SwingPoint.
        """

        self._add_level(swing)

        buy_side = self._detect_buy_side_sweep(swing)

        if buy_side is not None:
            return buy_side

        sell_side = self._detect_sell_side_sweep(swing)

        if sell_side is not None:
            return sell_side

        return None

    def _add_level(
        self,
        swing: SwingPoint,
    ) -> None:
        """
        Register a liquidity level from a confirmed swing.
        """

        level = LiquidityLevel(
            timestamp=swing.timestamp,
            price=swing.price,
            swing_point=swing,
            is_buy_side=(
                swing.swing_type.name == "HIGH"
            ),
        )

        self.state.liquidity_levels.append(level)
        self.state.processed_swing_count += 1

    def get_last_sweep(
        self,
    ) -> LiquiditySweepEvent | None:
        """
        Return the most recent confirmed liquidity sweep.
        """

        return self.state.last_sweep

    def _detect_buy_side_sweep(
        self,
        swing: SwingPoint,
    ) -> LiquiditySweepEvent | None:
        """
        Detect a buy-side liquidity sweep.
        """

        if swing.swing_type.name != "HIGH":
            return None

        for level in reversed(self.state.liquidity_levels[:-1]):
            if not level.is_buy_side:
                continue

            required_break = (
                level.price
                + self.config.minimum_sweep_distance
            )

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
        """
        Detect a sell-side liquidity sweep.
        """

        if swing.swing_type.name != "LOW":
            return None

        for level in reversed(self.state.liquidity_levels[:-1]):
            if level.is_buy_side:
                continue

            required_break = (
                level.price
                - self.config.minimum_sweep_distance
            )

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

    def _calculate_sweep_distance(
        self,
        *,
        level: LiquidityLevel,
        sweep_price: float,
    ) -> float:
        """
        Calculate the absolute sweep distance beyond
        the liquidity level.
        """

        return abs(
            sweep_price - level.price
        )

    def _create_sweep_event(
        self,
        *,
        level: LiquidityLevel,
        sweep_price: float,
        confirmation_index: int,
        sweep_distance: float,
    ) -> LiquiditySweepEvent | None:
        """
        Create and store a confirmed liquidity sweep event.
        """

        event = LiquiditySweepEvent(
            timestamp=level.timestamp,
            liquidity_level=level,
            sweep_price=sweep_price,
            confirmation_index=confirmation_index,
            sweep_distance=sweep_distance,
        )

        if not self._validate_sweep(event):
            return None

        self.state.confirmed_sweeps.append(event)
        self.state.last_sweep = event
        self.state.detector_status = DetectorStatus.BREAK_CONFIRMED

        return event

    def _validate_sweep(
        self,
        event: LiquiditySweepEvent,
    ) -> bool:
        """
        Validate a liquidity sweep event.

        Version 1 performs duplicate-event protection only.
        """

        last_sweep = self.state.last_sweep

        if last_sweep is None:
            return True

        if (
            last_sweep.liquidity_level == event.liquidity_level
            and last_sweep.sweep_price == event.sweep_price
        ):
            return False

        return True

    def get_sweeps(
        self,
    ) -> list[LiquiditySweepEvent]:
        """
        Return all confirmed liquidity sweeps.
        """

        return list(self.state.confirmed_sweeps)

    def get_state(
        self,
    ) -> LiquidityDetectorState:
        """
        Return the detector runtime state.
        """

        return self.state