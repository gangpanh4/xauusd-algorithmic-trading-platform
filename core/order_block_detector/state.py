"""
Runtime state for the Order Block Detection Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.market_structure.enums import (
    DetectorStatus,
)
from core.order_block_detector.models import (
    OrderBlock,
    OrderBlockCandidate,
    OrderBlockEvent,
)


@dataclass(slots=True)
class OrderBlockDetectorState:
    """
    Mutable runtime state owned exclusively by the OrderBlockDetector.

    This class stores the lifecycle of confirmed Order Blocks and
    detector runtime information.

    It contains no detection logic.
    """

    # Candidate Order Blocks awaiting validation.
    pending_candidates: list[OrderBlockCandidate] = field(
        default_factory=list
    )

    # All confirmed Order Blocks.
    confirmed_order_blocks: list[OrderBlock] = field(
        default_factory=list
    )

    # Currently active Order Blocks.
    active_order_blocks: list[OrderBlock] = field(
        default_factory=list
    )

    # Mitigated Order Blocks.
    mitigated_order_blocks: list[OrderBlock] = field(
        default_factory=list
    )

    # Invalidated Order Blocks.
    invalidated_order_blocks: list[OrderBlock] = field(
        default_factory=list
    )

    # Expired Order Blocks.
    expired_order_blocks: list[OrderBlock] = field(
        default_factory=list
    )

    # Confirmed lifecycle events.
    confirmed_events: list[OrderBlockEvent] = field(
        default_factory=list
    )

    # Most recently confirmed lifecycle event.
    last_event: OrderBlockEvent | None = None

    # Human-readable detector status.
    detector_status: DetectorStatus = DetectorStatus.WAITING

    # Total number of processed structural breaks.
    processed_break_count: int = 0

    # Deterministic Order Block identifier.
    next_block_id: int = 1

    def reset(self) -> None:
        """
        Reset the detector state.
        """

        self.pending_candidates.clear()

        self.confirmed_order_blocks.clear()
        self.active_order_blocks.clear()
        self.mitigated_order_blocks.clear()
        self.invalidated_order_blocks.clear()
        self.expired_order_blocks.clear()

        self.confirmed_events.clear()

        self.last_event = None

        self.detector_status = DetectorStatus.WAITING

        self.processed_break_count = 0

        self.next_block_id = 1