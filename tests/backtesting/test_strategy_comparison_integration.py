from __future__ import annotations

from datetime import UTC, datetime

from core.backtesting.engine import BacktestingEngine
from core.backtesting.models import BacktestResult
from core.backtesting.strategy_comparison import BacktestStrategyComparison
from core.backtesting.strategy_observer import BacktestStrategyObserver
from core.trading_pipeline.models import (
    PipelineDisposition,
    PipelineObservationAudit,
    PipelineStage,
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


def _engine() -> BacktestingEngine:
    engine = object.__new__(BacktestingEngine)
    engine.strategy_observer = BacktestStrategyObserver()
    engine._observation_audits = []
    return engine


def test_engine_builds_comparison_from_owned_histories() -> None:
    engine = _engine()
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    engine._observation_audits.append(
        PipelineObservationAudit(
            timestamp=timestamp,
            disposition=PipelineDisposition.ACCEPTED,
            stage_reached=PipelineStage.APPROVED,
            risk_approved=True,
        )
    )

    comparison = engine.build_strategy_comparison(_result())

    assert isinstance(comparison, BacktestStrategyComparison)
    assert comparison.pipeline_observation_count == 1
    assert comparison.pipeline_approval_count == 1
    assert comparison.executed_trade_count == 0
    assert comparison.strategy_observation_count == 0
    assert comparison.strategy_candidate_count == 0


def test_build_strategy_comparison_is_read_only() -> None:
    engine = _engine()
    result = _result()
    audits_before = engine.observation_audits
    strategy_before = engine.strategy_observations

    first = engine.build_strategy_comparison(result)
    second = engine.build_strategy_comparison(result)

    assert first == second
    assert engine.observation_audits == audits_before
    assert engine.strategy_observations == strategy_before
    assert result.total_trades == 0


def test_engine_comparison_rejects_invalid_result_type() -> None:
    engine = _engine()

    try:
        engine.build_strategy_comparison(object())  # type: ignore[arg-type]
    except TypeError as exc:
        assert 'BacktestResult' in str(exc)
    else:
        raise AssertionError('TypeError was not raised')
