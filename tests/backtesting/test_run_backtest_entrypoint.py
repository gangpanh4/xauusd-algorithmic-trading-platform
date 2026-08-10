from __future__ import annotations

import importlib
import sys
from datetime import UTC, datetime
from types import ModuleType, SimpleNamespace

from core.backtesting.config import BacktestExecutionModel
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


def test_run_backtest_uses_bounded_composite_research_path(
    monkeypatch,
    capsys,
) -> None:
    calls: list[tuple[str, object]] = []
    result = _result()
    output = SimpleNamespace(result=result)

    mt5_stub = ModuleType("MetaTrader5")
    mt5_stub.TIMEFRAME_M5 = 5
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
            end_time: datetime,
        ):
            calls.append(
                (
                    "run_with_strategy_comparison",
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "bars": bars,
                        "end_time": end_time,
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

    expected_end_time = datetime(
        2026,
        4,
        9,
        23,
        59,
        tzinfo=UTC,
    )
    assert module.HISTORICAL_BARS == 20_000
    assert module.HISTORICAL_END_TIME == expected_end_time
    config = calls[0][1]
    assert config.execution_model is BacktestExecutionModel.M5_COMPLETED_OHLC_V2
    assert calls[1] == (
        "run_with_strategy_comparison",
        {
            "symbol": "XAUUSD",
            "timeframe": 5,
            "bars": 20_000,
            "end_time": expected_end_time,
        },
    )
    assert calls[2] == ("generate_composite_reports", output)
    assert calls[-1] == ("shutdown", None)

    stdout = capsys.readouterr().out
    assert "XAUUSD HISTORICAL BACKTEST" in stdout
    assert "Bars requested  : 20,000" in stdout
    assert "2026-04-09T23:59:00+00:00" in stdout
    assert "Execution model : M5_COMPLETED_OHLC_V2" in stdout
    assert "Trades          : 1" in stdout
    assert "Win Rate        : 100.00%" in stdout
    assert "Net Profit      : 155.82" in stdout
    assert "Reports exported to:" in stdout


def test_run_backtest_shuts_down_mt5_when_composite_run_fails(
    monkeypatch,
) -> None:
    calls: list[str] = []

    mt5_stub = ModuleType("MetaTrader5")
    mt5_stub.TIMEFRAME_M5 = 5
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


def test_run_backtest_uses_pinned_offline_execution_profile(
    monkeypatch,
) -> None:
    captured: list[object] = []

    mt5_stub = ModuleType("MetaTrader5")
    mt5_stub.TIMEFRAME_M5 = 5
    mt5_stub.TIMEFRAME_M15 = 15
    mt5_stub.initialize = lambda: True
    mt5_stub.shutdown = lambda: None
    mt5_stub.last_error = lambda: (0, "OK")
    monkeypatch.setitem(sys.modules, "MetaTrader5", mt5_stub)

    specification_module = importlib.import_module(
        "core.mt5_execution.symbol_specification"
    )
    monkeypatch.setattr(
        specification_module,
        "get_live_symbol_specification",
        lambda symbol: (_ for _ in ()).throw(
            AssertionError(
                "historical entrypoint must not fetch current symbol metadata"
            )
        ),
    )

    class RunnerStub:
        def __init__(self, config) -> None:
            captured.append(config)

        def run_with_strategy_comparison(self, **kwargs):
            return SimpleNamespace(result=_result())

        def generate_composite_reports(self, output) -> None:
            pass

    runner_module = importlib.import_module("core.backtesting.runner")
    monkeypatch.setattr(runner_module, "BacktestRunner", RunnerStub)

    sys.modules.pop("run_backtest", None)
    module = importlib.import_module("run_backtest")
    module.main()

    config = captured[0]
    profile = config.resolved_execution_profile()
    assert config.execution_profile is profile
    assert config.execution_model is BacktestExecutionModel.M5_COMPLETED_OHLC_V2
    assert profile.instrument.minimum_volume == 0.01
    assert profile.instrument.maximum_volume == 10.0
    assert profile.instrument.contract_size is None
    assert profile.instrument.provenance.value == (
        "CURRENT_SNAPSHOT_ASSUMPTION"
    )
    assert profile.instrument.historical_specification_verified is False
    assert profile.historical_price_side.value == "UNKNOWN_SINGLE_PRICE"
    assert profile.parity_claims.volume_parity is False
