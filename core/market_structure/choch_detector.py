"""
Streaming Change of Character (CHOCH) Detection Engine.

The detector consumes confirmed SwingPoint objects and emits
confirmed CHOCHEvent objects whenever a valid Change of Character
is detected.
"""

from __future__ import annotations

from core.market_structure.config import CHOCHDetectorConfig
from core.market_structure.enums import (
    BreakType,
    DetectorStatus,
    MarketTrend,
    SwingType,
    TrendDirection,
)
from core.market_structure.models import (
    CHOCHEvent,
    SwingPoint,
)
from core.market_structure.state import (
    BOSDetectorState,
    CHOCHDetectorState,
)


class CHOCHDetector:
    """
    Streaming Change of Character (CHOCH) Detection Engine.

    The detector consumes confirmed SwingPoint objects and emits
    confirmed CHOCHEvent objects whenever a valid Change of Character
    is detected.
    """

    def __init__(
        self,
        bos_state: BOSDetectorState,
        config: CHOCHDetectorConfig | None = None,
    ) -> None:
        """
        Initialize the Change of Character Detector.
        """

        self.config = config or CHOCHDetectorConfig()

        self.bos_state = bos_state

        self.state = CHOCHDetectorState()

    def reset(self) -> None:
        """
        Reset the detector state.
        """

        self.state.reset()

    def process(
        self,
        swing: SwingPoint,
    ) -> CHOCHEvent | None:
        """
        Process one confirmed SwingPoint.

        Returns a CHOCHEvent only when a valid
        Change of Character has been confirmed.
        """

        self._add_swing(swing)

        bearish_event = self._detect_bearish_choch(swing)

        if bearish_event is not None:
            return bearish_event

        bullish_event = self._detect_bullish_choch(swing)

        if bullish_event is not None:
            return bullish_event

        return None

    def _add_swing(
        self,
        swing: SwingPoint,
    ) -> None:
        """
        Store a confirmed swing and update detector state.
        """

        self.state.confirmed_swings.append(swing)
        self.state.processed_swing_count += 1
        self.state.detector_status = DetectorStatus.RUNNING

    def _has_enough_swings(
        self,
    ) -> bool:
        """
        Return True once enough confirmed swings have been received
        to evaluate a Change of Character.
        """

        return len(self.state.confirmed_swings) >= 2

    def _get_previous_same_type(
        self,
        swing: SwingPoint,
    ) -> SwingPoint | None:
        """
        Return the most recent confirmed swing having the same
        SwingType as the supplied swing.

        The current swing itself is excluded from the search.
        """

        if len(self.state.confirmed_swings) < 2:
            return None

        for previous in reversed(self.state.confirmed_swings[:-1]):
            if previous.swing_type is swing.swing_type:
                return previous

        return None

    def _get_current_trend(
        self,
    ) -> MarketTrend:
        """
        Return the current market trend from BOS state.
        """

        return self.bos_state.current_trend

    def _get_protected_swing(
        self,
    ) -> SwingPoint | None:
        """
        Return the protected swing from BOS state.
        """

        return self.bos_state.protected_swing

    def _calculate_break_distance(
        self,
        current: SwingPoint,
        protected: SwingPoint,
    ) -> float:
        """
        Calculate the absolute distance beyond the
        protected swing.

        Version 2 uses this metric as the foundation
        for future CHOCH quality scoring.
        """

        return abs(
            current.price - protected.price
        )

    def _detect_bearish_choch(
        self,
        swing: SwingPoint,
    ) -> CHOCHEvent | None:
        """
        Detect bearish Change of Character.

        Happens when bullish structure is broken by
        a confirmed swing low below the protected swing.
        """

        if self._get_current_trend() is not MarketTrend.BULLISH:
            return None

        if swing.swing_type is not SwingType.LOW:
            return None

        protected_swing = self._get_protected_swing()

        if protected_swing is None:
            return None

        if swing.price >= protected_swing.price:
            return None

        break_distance = self._calculate_break_distance(
            current=swing,
            protected=protected_swing,
        )

        return self._create_choch_event(
            swing=swing,
            break_type=BreakType.CHOCH,
            break_distance=break_distance,
        )

    def _detect_bullish_choch(
        self,
        swing: SwingPoint,
    ) -> CHOCHEvent | None:
        """
        Detect bullish Change of Character.

        Happens when bearish structure is broken by
        a confirmed swing high above the protected swing.
        """

        if self._get_current_trend() is not MarketTrend.BEARISH:
            return None

        if swing.swing_type is not SwingType.HIGH:
            return None

        protected_swing = self._get_protected_swing()

        if protected_swing is None:
            return None

        if swing.price <= protected_swing.price:
            return None

        break_distance = self._calculate_break_distance(
            current=swing,
            protected=protected_swing,
        )

        return self._create_choch_event(
            swing=swing,
            break_type=BreakType.CHOCH,
            break_distance=break_distance,
        )

    def _create_choch_event(
        self,
        *,
        swing: SwingPoint,
        break_type: BreakType,
        break_distance: float,
    ) -> CHOCHEvent | None:
        """
        Create and store a confirmed CHOCH event.
        """

        if swing.swing_type is SwingType.HIGH:
            direction = TrendDirection.BULLISH
        else:
            direction = TrendDirection.BEARISH

        event = CHOCHEvent(
            timestamp=swing.timestamp,
            break_type=break_type,
            direction=direction,
            break_price=swing.price,
            swing_point=swing,
            confirmation_index=swing.confirmation_index,
            break_distance=break_distance,
        )

        if not self._validate_change(event):
            return None

        self.state.confirmed_changes.append(event)
        self.state.last_change = event
        self.state.detector_status = DetectorStatus.BREAK_CONFIRMED

        return event

    def _validate_change(
        self,
        event: CHOCHEvent,
    ) -> bool:
        """
        Validate a confirmed CHOCH event.

        Version 1 performs duplicate-event protection only.
        """

        last_change = self.state.last_change

        if last_change is None:
            return True

        if (
            last_change.break_type is event.break_type
            and last_change.swing_point == event.swing_point
        ):
            return False

        return True

    def _update_trend(
        self,
    ) -> None:
        """
        Update the current confirmed market trend.
        """

        pass

    def _update_protected_swing(
        self,
        swing: SwingPoint,
    ) -> None:
        """
        Update the protected swing used for CHOCH detection.
        """

        pass

    def _is_bullish_trend(
        self,
    ) -> bool:
        """
        Return True if the current trend is bullish.
        """

        return (
            self.state.current_trend
            is MarketTrend.BULLISH
        )

    def _is_bearish_trend(
        self,
    ) -> bool:
        """
        Return True if the current trend is bearish.
        """

        return (
            self.state.current_trend
            is MarketTrend.BEARISH
        )