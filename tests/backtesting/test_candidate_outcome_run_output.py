from __future__ import annotations

from types import MappingProxyType

from core.backtesting.candidate_outcome_models import CandidateOutcome
from core.backtesting.candidate_outcome_tracker import (
    CandidateOutcomeTracker,
)
from core.backtesting.engine import BacktestingEngine
from core.backtesting.models import BacktestResult
from core.backtesting.run_output import BacktestRunOutput
from core.backtesting.strategy_comparison import BacktestStrategyComparison

from tests.backtesting.test_candidate_outcome_evaluator import (
    _candidate,
)


def _result() -> BacktestResult:
    return BacktestResult(
        total_trades=0,
        winning_trades=0,
        losing_trades=0,
        breakeven_trades=0,
        net_profit=0.0,
        win_rate=0.0,
        max_drawdown=0.0,
    )


def _comparison() -> BacktestStrategyComparison:
    return BacktestStrategyComparison(
        pipeline_observation_count=0,
        pipeline_approval_count=0,
        executed_trade_count=0,
        strategy_observation_count=0,
        strategy_setup_count=0,
        strategy_candidate_count=0,
        pipeline_reason_counts=(),
        strategy_reason_counts=(),
        events=(),
    )


def test_run_output_preserves_two_argument_construction() -> None:
    output = BacktestRunOutput(
        result=_result(),
        strategy_comparison=_comparison(),
    )

    assert output.candidate_outcome_evaluations == ()
    assert dict(output.candidate_outcome_summary) == {}
    assert isinstance(output.candidate_outcome_summary, MappingProxyType)


def test_run_output_freezes_candidate_outcome_research() -> None:
    tracker = CandidateOutcomeTracker()
    tracker.register(_candidate())
    evaluations = tracker.finalize()
    summary = tracker.summary()

    output = BacktestRunOutput(
        result=_result(),
        strategy_comparison=_comparison(),
        candidate_outcome_evaluations=evaluations,
        candidate_outcome_summary=summary,
    )
    summary["UNRESOLVED"] = 99

    assert output.candidate_outcome_evaluations == evaluations
    assert output.candidate_outcome_summary["UNRESOLVED"] == 1
    assert (
        output.candidate_outcome_evaluations[0].outcome
        is CandidateOutcome.UNRESOLVED
    )


def test_engine_composite_output_includes_candidate_outcomes() -> None:
    engine = object.__new__(BacktestingEngine)
    engine.candidate_outcome_tracker = CandidateOutcomeTracker()
    engine.candidate_outcome_tracker.register(_candidate())
    engine.candidate_outcome_tracker.finalize()

    result = _result()
    comparison = _comparison()
    context = object()
    engine.run = lambda received: result
    engine.build_strategy_comparison = lambda received: comparison

    output = engine.run_with_strategy_comparison(context)

    assert output.result is result
    assert output.strategy_comparison is comparison
    assert len(output.candidate_outcome_evaluations) == 1
    assert output.candidate_outcome_summary["UNRESOLVED"] == 1
