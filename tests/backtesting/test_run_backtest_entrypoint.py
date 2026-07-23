from __future__ import annotations

import importlib
import sys
from types import ModuleType, SimpleNamespace

from core.backtesting.models import BacktestResult


def _result() -> BacktestResult:
    return BacktestResult(
        total_trades=1,
        winning_trades=1,
        losing_trades=0,
        breakeven_trades=0,
        net_profit=155.82,
        win_rate=100.0,
        max_drawdown=0.0,
    )


def test_run_backtest_uses_composite_research_path(
    monkeypatch,
    capsys,
) -> None:
    calls: list[tuple[str, object]] = []
    result = _result()
    output = SimpleNamespace(result=result)

    mt5_stub = ModuleType("MetaTrader5")
    mt5_stub.TIMEFRAME_M15 = 15
    mt5_stub.initialize = lambda: True
    mt5_stub.shutdown = lambda: calls.append(("shutdown", None))
    mt5_stub.last_error = lambda: (0, "OK")
    monkeypatch.setitem(sys.modules, "MetaTrader5", mt5_stub)

    class RunnerStub:
        def __init__(self, config) -> None:
            calls.append(("init", config))

        def run_with_strategy_comparison(
            self,
            *,
            symbol: str,
            timeframe: int,
            bars: int,
        ):
            calls.append(
                (
                    "run_with_strategy_comparison",
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "bars": bars,
                    },
                )
            )
            return output

        def generate_composite_reports(self, received) -> None:
            calls.append(("generate_composite_reports", received))

        def run(self, *args, **kwargs):
            raise AssertionError("legacy runner.run path must not be used")

        def generate_reports(self, *args, **kwargs):
            raise AssertionError(
                "legacy runner.generate_reports path must not be used"
            )

    runner_module = importlib.import_module("core.backtesting.runner")
    monkeypatch.setattr(runner_module, "BacktestRunner", RunnerStub)

    sys.modules.pop("run_backtest", None)
    module = importlib.import_module("run_backtest")
    module.main()

    assert calls[1] == (
        "run_with_strategy_comparison",
        {
            "symbol": "XAUUSD",
            "timeframe": 15,
            "bars": 5_000,
        },
    )
    assert calls[2] == ("generate_composite_reports", output)
    assert calls[-1] == ("shutdown", None)

    stdout = capsys.readouterr().out
    assert "XAUUSD HISTORICAL BACKTEST" in stdout
    assert "Trades          : 1" in stdout
    assert "Win Rate        : 100.00%" in stdout
    assert "Net Profit      : 155.82" in stdout
    assert "Reports exported to:" in stdout


def test_run_backtest_shuts_down_mt5_when_composite_run_fails(
    monkeypatch,
) -> None:
    calls: list[str] = []

    mt5_stub = ModuleType("MetaTrader5")
    mt5_stub.TIMEFRAME_M15 = 15
    mt5_stub.initialize = lambda: True
    mt5_stub.shutdown = lambda: calls.append("shutdown")
    mt5_stub.last_error = lambda: (0, "OK")
    monkeypatch.setitem(sys.modules, "MetaTrader5", mt5_stub)

    class RunnerStub:
        def __init__(self, config) -> None:
            pass

        def run_with_strategy_comparison(self, **kwargs):
            raise RuntimeError("composite failure")

    runner_module = importlib.import_module("core.backtesting.runner")
    monkeypatch.setattr(runner_module, "BacktestRunner", RunnerStub)

    sys.modules.pop("run_backtest", None)
    module = importlib.import_module("run_backtest")

    try:
        module.main()
    except RuntimeError as error:
        assert str(error) == "composite failure"
    else:
        raise AssertionError("expected composite failure")

    assert calls == ["shutdown"]
