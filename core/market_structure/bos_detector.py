"""
Streaming Break of Structure (BOS) Detection Engine.
"""

from __future__ import annotations

from core.market_structure.config import BOSDetectorConfig
from core.market_structure.enums import (
    BreakType,
    DetectorStatus,
    SwingType,
)
from core.market_structure.models import BOSEvent, SwingPoint
from core.market_structure.state import BOSDetectorState


class BOSDetector:
    """
    Streaming Break of Structure (BOS) Detection Engine.

    The detector consumes confirmed SwingPoint objects and emits
    confirmed BOSEvent objects whenever a valid Break of Structure
    is detected.
    """

    def __init__(
        self,
        config: BOSDetectorConfig | None = None,
    ) -> None:
        """
        Initialize the Break of Structure Detector.
        """

        self.config = config or BOSDetectorConfig()
        self.state = BOSDetectorState()

    def reset(
        self,
    ) -> None:
        """
        Reset the BOS detector state.
        """

        self.state.reset()

    def process(
        self,
        swing: SwingPoint,
    ) -> BOSEvent | None:
        """
        Process one confirmed SwingPoint.

        Returns a BOSEvent only when a valid Break of Structure
        has been confirmed.
        """

        self._add_swing(swing)

        if not self._has_enough_swings():
            return None

        bullish_event = self._detect_bullish_bos(swing)
        if bullish_event is not None:
            return bullish_event

        bearish_event = self._detect_bearish_bos(swing)
        if bearish_event is not None:
            return bearish_event

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
        to evaluate a Break of Structure.
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

    def _detect_bullish_bos(
        self,
        swing: SwingPoint,
    ) -> BOSEvent | None:
        """
        Detect a bullish Break of Structure.
        """

        if swing.swing_type is not SwingType.HIGH:
            return None

        previous_high = self._get_previous_same_type(swing)

        if previous_high is None:
            return None

        required_break = (
            previous_high.price
            + self.config.minimum_break_distance
        )

        if swing.price <= required_break:
            return None

        return self._create_bos_event(
            swing=swing,
        )

    def _detect_bearish_bos(
        self,
        swing: SwingPoint,
    ) -> BOSEvent | None:
        """
        Detect a bearish Break of Structure.
        """

        if swing.swing_type is not SwingType.LOW:
            return None

        previous_low = self._get_previous_same_type(swing)

        if previous_low is None:
            return None

        required_break = (
            previous_low.price
            - self.config.minimum_break_distance
        )

        if swing.price >= required_break:
            return None

        return self._create_bos_event(
            swing=swing,
        )

    def _create_bos_event(
        self,
        swing: SwingPoint,
    ) -> BOSEvent | None:
        """
        Create and store a confirmed Break of Structure event.
        """

        event = BOSEvent(
            timestamp=swing.timestamp,
            break_type=BreakType.BOS,
            swing_point=swing,
            confirmation_index=swing.confirmation_index,
        )

        if not self._validate_break(event):
            return None

        self.state.confirmed_breaks.append(event)
        self.state.last_break = event
        self.state.detector_status = DetectorStatus.BREAK_CONFIRMED

        return event

    def _validate_break(
        self,
        event: BOSEvent,
    ) -> bool:
        """
        Validate a confirmed Break of Structure event.

        Version 1 performs duplicate-event protection only.
        """

        for previous in self.state.confirmed_breaks:
            if (
                previous.break_type is event.break_type
                and previous.swing_point == event.swing_point
            ):
                return False

        return True

    def get_last_break(
        self,
    ) -> BOSEvent | None:
        """
        Return the most recently confirmed BOS.
        """

        return self.state.last_break

    def get_breaks(
        self,
    ) -> list[BOSEvent]:
        """
        Return every confirmed BOS detected so far.
        """

        return list(self.state.confirmed_breaks)

    def get_state(
        self,
    ) -> BOSDetectorState:
        """
        Return the detector runtime state.
        """

        return self.state