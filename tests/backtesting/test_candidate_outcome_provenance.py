from __future__ import annotations

from core.backtesting.candidate_outcome_evaluator import CandidateOutcomeEvaluator
from core.strategies import SetupDirection

from tests.backtesting.test_candidate_outcome_evaluator import (
    _bar,
    _candidate,
)


def test_evaluation_preserves_candidate_research_provenance() -> None:
    candidate = _candidate()
    evaluation = CandidateOutcomeEvaluator().evaluate(
        candidate,
        (
            _bar(
                5,
                high=3305.0,
                low=3298.0,
            ),
        ),
    )

    assert evaluation.strategy_id == candidate.setup.strategy_id
    assert evaluation.direction is SetupDirection.BUY
    assert evaluation.setup_timeframe is candidate.setup.setup_timeframe
    assert evaluation.trigger_timeframe is candidate.trigger.timeframe
    assert evaluation.trigger_reason == candidate.trigger.reason
    assert dict(evaluation.setup_metadata) == dict(candidate.setup.metadata)
    assert dict(evaluation.trigger_metadata) == dict(
        candidate.trigger.metadata
    )
    assert dict(evaluation.candidate_metadata) == dict(candidate.metadata)
