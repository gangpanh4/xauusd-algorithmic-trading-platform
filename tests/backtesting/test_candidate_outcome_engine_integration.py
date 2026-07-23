from __future__ import annotations

from core.backtesting.candidate_outcome_models import CandidateOutcome
from core.backtesting.candidate_outcome_tracker import (
    CandidateOutcomeTracker,
)
from core.backtesting.engine import BacktestingEngine

from tests.backtesting.test_candidate_outcome_evaluator import (
    _candidate,
)


def test_engine_exposes_immutable_candidate_outcomes() -> None:
    engine = object.__new__(BacktestingEngine)
    engine.candidate_outcome_tracker = CandidateOutcomeTracker()
    engine.candidate_outcome_tracker.register(_candidate())
    engine.candidate_outcome_tracker.finalize()

    evaluations = engine.candidate_outcome_evaluations

    assert isinstance(evaluations, tuple)
    assert len(evaluations) == 1
    assert evaluations[0].outcome is CandidateOutcome.UNRESOLVED
    assert engine.candidate_outcome_summary()["UNRESOLVED"] == 1
