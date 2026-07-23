from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.backtesting.candidate_outcome_models import CandidateOutcome
from core.backtesting.candidate_outcome_tracker import (
    CandidateOutcomeTracker,
)
from core.data.models import MarketBar

from tests.backtesting.test_candidate_outcome_evaluator import (
    _candidate,
)


def _bar(
    minutes: int,
    *,
    high: float,
    low: float,
) -> MarketBar:
    return MarketBar(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC)
        + timedelta(minutes=minutes),
        open=3300.0,
        high=high,
        low=low,
        close=3300.0,
        tick_volume=100,
    )


def test_tracker_advances_candidate_incrementally() -> None:
    tracker = CandidateOutcomeTracker()
    candidate = _candidate()
    tracker.register(candidate)

    tracker.process_bar(
        MarketBar(
            timestamp=candidate.created_at,
            open=3300.0,
            high=3350.0,
            low=3250.0,
            close=3300.0,
            tick_volume=100,
        )
    )
    assert tracker.pending_count == 1
    assert tracker.evaluations == ()

    tracker.process_bar(_bar(5, high=3310.0, low=3298.0))
    assert tracker.pending_count == 1

    tracker.process_bar(_bar(10, high=3321.0, low=3297.0))

    assert tracker.pending_count == 0
    assert len(tracker.evaluations) == 1
    assert (
        tracker.evaluations[0].outcome
        is CandidateOutcome.TARGET_REACHED
    )
    assert tracker.evaluations[0].bars_evaluated == 2


def test_tracker_finalizes_unresolved_candidates() -> None:
    tracker = CandidateOutcomeTracker()
    tracker.register(_candidate())
    tracker.process_bar(_bar(5, high=3310.0, low=3298.0))

    evaluations = tracker.finalize()

    assert tracker.pending_count == 0
    assert len(evaluations) == 1
    assert evaluations[0].outcome is CandidateOutcome.UNRESOLVED
    assert tracker.summary() == {
        "TARGET_REACHED": 0,
        "STOP_REACHED": 0,
        "AMBIGUOUS_SAME_BAR": 0,
        "UNRESOLVED": 1,
    }


def test_tracker_reset_clears_pending_and_completed_state() -> None:
    tracker = CandidateOutcomeTracker()
    tracker.register(_candidate())
    tracker.process_bar(_bar(5, high=3321.0, low=3297.0))
    assert tracker.evaluations

    tracker.reset()

    assert tracker.pending_count == 0
    assert tracker.evaluations == ()
