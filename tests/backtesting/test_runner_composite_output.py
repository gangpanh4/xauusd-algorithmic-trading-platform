from __future__ import annotations

from types import SimpleNamespace

import MetaTrader5 as mt5
import pytest

from core.backtesting.config import BacktestConfig
from core.backtesting.models import BacktestResult
from core.backtesting.run_output import BacktestRunOutput
from core.backtesting.runner import BacktestRunner
from core.backtesting.strategy_comparison import BacktestStrategyComparison


def _result(total_trades: int = 2) -> BacktestResult:
    return BacktestResult(
        total_trades=total_trades,
        winning_trades=1,
        losing_trades=1,
        breakeven_trades=0,
        net_profit=0.0,
        win_rate=50.0,
        max_drawdown=0.0,
    )


def _comparison(total_trades: int = 2) -> BacktestStrategyComparison:
    return BacktestStrategyComparison(
        pipeline_observation_count=10,
        pipeline_approval_count=2,
        executed_trade_count=total_trades,
        strategy_observation_count=10,
        strategy_setup_count=1,
        strategy_candidate_count=1,
        pipeline_reason_counts=(),
        strategy_reason_counts=(),
        events=(),
    )


def _runner_without_init() -> BacktestRunner:
    runner = object.__new__(BacktestRunner)
    runner.config = BacktestConfig()
    runner.state = SimpleNamespace(
        processed_bar_count=99,
        executed_trade_count=99,
        completed=True,
        reset=lambda: None,
    )
    return runner


def test_runner_composite_method_loads_once_and_updates_state() -> None:
    runner = _runner_without_init()
    context = SimpleNamespace(
        m5_bars=(object(), object(), object()),
        m15_bars=(object(),),
        h1_bars=(object(),),
        h4_bars=(object(),),
    )
    result = _result(total_trades=2)
    output = BacktestRunOutput(
        result=result,
        strategy_comparison=_comparison(total_trades=2),
    )
    load_calls: list[dict[str, object]] = []
    engine_calls: list[object] = []

    class Loader:
        def load(self, **kwargs: object) -> object:
            load_calls.append(dict(kwargs))
            return context

    class Engine:
        multi_timeframe_window_bars = 500

        def run_with_strategy_comparison(
            self,
            received_context: object,
        ) -> BacktestRunOutput:
            engine_calls.append(received_context)
            return output

    runner.loader = Loader()
    runner.engine = Engine()

    received = runner.run_with_strategy_comparison(
        symbol="XAUUSD",
        timeframe=mt5.TIMEFRAME_M5,
        bars=500,
    )

    assert received is output
    assert load_calls == [
        {
            "symbol": "XAUUSD",
            "bars": 500,
            "end_time": None,
            "warmup_bars": 200,
            "analysis_window_bars": 500,
        }
    ]
    assert engine_calls == [context]
    assert runner.state.processed_bar_count == 3
    assert runner.state.executed_trade_count == 2
    assert runner.state.completed is True


def test_runner_composite_method_rejects_empty_m5_history() -> None:
    runner = _runner_without_init()
    runner.loader = SimpleNamespace(
        load=lambda **_: SimpleNamespace(m5_bars=()),
    )
    runner.engine = SimpleNamespace(
        run_with_strategy_comparison=lambda _: pytest.fail(
            "engine should not run without M5 history"
        )
    )

    with pytest.raises(RuntimeError, match="No historical data"):
        runner.run_with_strategy_comparison(
            symbol="XAUUSD",
            timeframe=mt5.TIMEFRAME_M5,
            bars=500,
        )


def test_existing_runner_run_contract_remains_backtest_result() -> None:
    annotations = BacktestRunner.run.__annotations__
    assert annotations.get("return") in {
        BacktestResult,
        "BacktestResult",
    }
