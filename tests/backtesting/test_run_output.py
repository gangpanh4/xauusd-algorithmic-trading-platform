from __future__ import annotations

from core.backtesting.engine import BacktestingEngine
from core.backtesting.models import BacktestResult
from core.backtesting.run_output import BacktestRunOutput
from core.backtesting.strategy_comparison import BacktestStrategyComparison


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


def test_run_output_validates_both_components() -> None:
    result = _result()
    comparison = _comparison()

    output = BacktestRunOutput(
        result=result,
        strategy_comparison=comparison,
    )

    assert output.result is result
    assert output.strategy_comparison is comparison


def test_engine_run_with_strategy_comparison_calls_run_once() -> None:
    engine = object.__new__(BacktestingEngine)
    result = _result()
    comparison = _comparison()
    calls: list[object] = []
    context = object()

    def fake_run(received_context: object) -> BacktestResult:
        calls.append(received_context)
        return result

    def fake_build(received_result: BacktestResult) -> BacktestStrategyComparison:
        assert received_result is result
        return comparison

    engine.run = fake_run  # type: ignore[method-assign]
    engine.build_strategy_comparison = fake_build  # type: ignore[method-assign]

    output = engine.run_with_strategy_comparison(context)  # type: ignore[arg-type]

    assert calls == [context]
    assert output.result is result
    assert output.strategy_comparison is comparison


def test_existing_run_contract_is_not_replaced() -> None:
    annotations = BacktestingEngine.run.__annotations__
    assert annotations.get('return') in {
        BacktestResult,
        'BacktestResult',
    }
