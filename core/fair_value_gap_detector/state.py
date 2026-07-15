"""
Fair Value Gap detector runtime state.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.fair_value_gap_detector.models import (
    FairValueGap,
    FairValueGapCandidate,
)


@dataclass(slots=True)
class FairValueGapDetectorState:
    """
    Runtime state of the Fair Value Gap detector.
    """

    # -------------------------------------------------
    # Detection
    # -------------------------------------------------

    pending_candidates: list[
        FairValueGapCandidate
    ] = field(default_factory=list)

    # -------------------------------------------------
    # Confirmed
    # -------------------------------------------------

    confirmed_gaps: list[
        FairValueGap
    ] = field(default_factory=list)

    # -------------------------------------------------
    # Lifecycle
    # -------------------------------------------------

    active_gaps: list[
        FairValueGap
    ] = field(default_factory=list)

    mitigated_gaps: list[
        FairValueGap
    ] = field(default_factory=list)

    invalidated_gaps: list[
        FairValueGap
    ] = field(default_factory=list)

    archived_gaps: list[
        FairValueGap
    ] = field(default_factory=list)

    # -------------------------------------------------
    # Statistics
    # -------------------------------------------------

    processed_count: int = 0

    next_gap_id: int = 1

    def reset(
        self,
    ) -> None:
        """
        Reset detector runtime state.
        """

        self.pending_candidates.clear()

        self.confirmed_gaps.clear()

        self.active_gaps.clear()

        self.mitigated_gaps.clear()

        self.invalidated_gaps.clear()

        self.archived_gaps.clear()

        self.processed_count = 0

        self.next_gap_id = 1