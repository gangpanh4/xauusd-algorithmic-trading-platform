"""
Streaming Swing Detection Engine.
"""

from __future__ import annotations

from core.data.market_data import MarketBar
from core.market_structure.config import SwingDetectorConfig
from core.market_structure.enums import SwingType
from core.market_structure.models import SwingPoint
from core.market_structure.state import SwingDetectorState


class SwingDetector:
    """
    Detects confirmed swing highs and swing lows from a stream of
    completed MarketBar objects.

    The detector owns its runtime state and processes one completed
    market bar at a time.
    """

    def __init__(
        self,
        config: SwingDetectorConfig | None = None,
    ) -> None:
        """
        Initialize the Swing Detector.
        """

        self.config = config or SwingDetectorConfig()
        self.state = SwingDetectorState()

    def reset(self) -> None:
        """
        Reset the detector to its initial state.
        """

        self.state.reset()

    def process(
        self,
        bar: MarketBar,
    ) -> SwingPoint | None:
        """
        Process one completed market bar.

        A confirmed SwingPoint is returned only after sufficient
        historical context exists.
        """

        self._add_bar(bar)

        if not self._has_enough_history():
            return None

        pivot = self._get_pivot_candidate()

        if self._is_swing_high(pivot):
            swing = self._create_swing_point(
                pivot,
                SwingType.HIGH,
            )

        elif self._is_swing_low(pivot):
            swing = self._create_swing_point(
                pivot,
                SwingType.LOW,
            )

        else:
            return None

        if not self._validate_swing(
            swing
        ):
            return None

        self.state.confirmed_swings.append(
            swing
        )

        self.state.last_swing = swing

        return swing

    def _add_bar(
        self,
        bar: MarketBar,
    ) -> None:
        """
        Append a completed market bar to the rolling history.
        """

        self.state.recent_bars.append(bar)
        self.state.processed_bar_count += 1

        while (
            len(self.state.recent_bars)
            > self.config.maximum_history
        ):
            self.state.recent_bars.popleft()

    def _has_enough_history(self) -> bool:
        """
        Determine whether enough bars exist to evaluate
        a pivot candidate.
        """

        required = (
            self.config.pivot_left
            + self.config.pivot_right
            + 1
        )

        return len(self.state.recent_bars) >= required

    def _get_pivot_candidate(
        self,
    ) -> MarketBar:
        """
        Return the current pivot candidate.

        The candidate is the center candle inside the
        rolling confirmation window.
        """

        bars = list(self.state.recent_bars)

        return bars[-(self.config.pivot_right + 1)]

    def _is_swing_high(
        self,
        pivot: MarketBar,
    ) -> bool:
        """
        Determine whether the specified pivot is a confirmed
        swing high.
        """

        bars = list(self.state.recent_bars)

        center_index = self.config.pivot_left

        tolerance = self.config.equal_high_tolerance

        # Validate left side.
        for bar in bars[:center_index]:
            if pivot.high < (bar.high + tolerance):
                return False

        # Validate right side.
        for bar in bars[center_index + 1 :]:
            if pivot.high < (bar.high + tolerance):
                return False

        return True

    def _is_swing_low(
        self,
        pivot: MarketBar,
    ) -> bool:
        """
        Determine whether the specified pivot is a confirmed
        swing low.
        """

        bars = list(self.state.recent_bars)

        center_index = self.config.pivot_left

        tolerance = self.config.equal_low_tolerance

        # Validate left side.
        for bar in bars[:center_index]:
            if pivot.low > (bar.low - tolerance):
                return False

        # Validate right side.
        for bar in bars[center_index + 1 :]:
            if pivot.low > (bar.low - tolerance):
                return False

        return True

    def _create_swing_point(
        self,
        pivot: MarketBar,
        swing_type: SwingType,
    ) -> SwingPoint:
        """
        Create a confirmed SwingPoint from the specified pivot.
        """

        pivot_index = (
            self.state.processed_bar_count
            - self.config.pivot_right
            - 1
        )

        price = (
            pivot.high
            if swing_type is SwingType.HIGH
            else pivot.low
        )

        return SwingPoint(
            timestamp=pivot.timestamp,
            index=pivot_index,
            price=price,
            swing_type=swing_type,
            confirmation_index=self.state.processed_bar_count - 1,
        )

    def _passes_minimum_distance(
        self,
        swing: SwingPoint,
    ) -> tuple[bool, float]:
        """
        Determine whether the swing satisfies the configured
        minimum swing distance.

        Returns both the validation result and the calculated
        swing distance so it can be reused by ATR validation.
        """

        if self.state.last_swing is None:
            return True, 0.0

        distance = abs(
            swing.price
            - self.state.last_swing.price
        )

        return (
            distance
            >= self.config.minimum_swing_distance,
            distance,
        )

    def _validate_swing(
        self,
        swing: SwingPoint,
    ) -> bool:
        """
        Validate a newly detected swing before accepting it.

        Validation includes:

        - Duplicate prevention
        - Alternating swing sequence
        - Minimum swing distance
        - ATR validation
        """

        if self.state.last_swing is not None:

            #
            # Reject duplicate swings.
            #
            if (
                swing.index == self.state.last_swing.index
                and swing.swing_type
                == self.state.last_swing.swing_type
            ):
                return False

            #
            # Enforce alternating swing sequence.
            #
            if (
                swing.swing_type
                == self.state.last_swing.swing_type
            ):
                return False

        #
        # Reject insignificant swings.
        #
        passes_distance, distance = (
            self._passes_minimum_distance(
                swing
            )
        )

        if not passes_distance:
            return False

        #
        # ATR validation.
        #
        if self.config.atr_validation:

            atr = self._calculate_atr()

            if atr is None:
                return False

            if (
                distance
                < atr * self.config.atr_multiplier
            ):
                return False

        return True

    def _calculate_true_range(
        self,
        current_bar: MarketBar,
        previous_bar: MarketBar,
    ) -> float:
        """
        Calculate the True Range (TR) for a single market bar.
        """

        return max(
            current_bar.high - current_bar.low,
            abs(current_bar.high - previous_bar.close),
            abs(current_bar.low - previous_bar.close),
        )

    def _calculate_atr(self) -> float | None:
        """
        Calculate the Average True Range (ATR) from the recent
        market history.

        Returns None if there is insufficient history.
        """

        bars = list(self.state.recent_bars)

        required = self.config.atr_period + 1

        if len(bars) < required:
            return None

        true_ranges: list[float] = []

        for i in range(1, required):
            true_ranges.append(
                self._calculate_true_range(
                    bars[-required + i],
                    bars[-required + i - 1],
                )
            )

        return sum(true_ranges) / len(true_ranges)

    def get_last_swing(
        self,
    ) -> SwingPoint | None:
        """
        Return the most recently confirmed swing.
        """

        return self.state.last_swing

    def get_swings(
        self,
    ) -> tuple[SwingPoint, ...]:
        """
        Return all confirmed swings.

        A tuple is returned to prevent callers from modifying the
        detector's internal state.
        """

        return tuple(self.state.confirmed_swings)

    def get_state(
        self,
    ) -> SwingDetectorState:
        """
        Return the current detector state.

        This method is primarily intended for diagnostics,
        debugging, and testing.
        """

        return self.state