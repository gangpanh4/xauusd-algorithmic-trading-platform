from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import MetaTrader5 as mt5

from core.backtesting.config import BacktestConfig
from core.backtesting.models import BacktestResult
from core.backtesting.runner import BacktestRunner
from core.regime_detector.models import MarketBar


def _bar(timestamp: datetime) -> MarketBar:
    return MarketBar(
        timestamp=timestamp,
        open=3000.0,
        high=3001.0,
        low=2999.0,
        close=3000.5,
        volume=100.0,
        tick_volume=100,
    )


def _context() -> SimpleNamespace:
    start = datetime(2026, 4, 9, 8, 0, tzinfo=UTC)
    return SimpleNamespace(
        m5_bars=[_bar(start), _bar(start + timedelta(minutes=5))],
        m15_bars=[_bar(start), _bar(start + timedelta(minutes=15))],
        h1_bars=[_bar(start), _bar(start + timedelta(hours=1))],
        h4_bars=[_bar(start), _bar(start + timedelta(hours=4))],
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


class _Engine:
    multi_timeframe_window_bars = 500

    def run(self, context: object) -> BacktestResult:
        return _result()


def test_runner_forwards_explicit_historical_boundary() -> None:
    boundary = datetime(2026, 4, 9, 12, 0, tzinfo=UTC)

    class Loader:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def load(self, **kwargs: object) -> SimpleNamespace:
            self.calls.append(dict(kwargs))
            return _context()

    runner = BacktestRunner(BacktestConfig())
    loader = Loader()
    runner.loader = loader
    runner.engine = _Engine()

    result = runner.run(
        symbol="XAUUSD",
        timeframe=mt5.TIMEFRAME_M5,
        bars=20_000,
        end_time=boundary,
    )

    assert result.total_trades == 0
    assert loader.calls == [
        {
            "symbol": "XAUUSD",
            "bars": 20_000,
            "end_time": boundary,
            "warmup_bars": 200,
            "analysis_window_bars": 500,
        }
    ]
    assert runner._last_requested_end_time == boundary
    assert runner._last_actual_window["requested_eligible_m5_bars"] == 20_000
    assert runner._last_actual_window["requested_end_time"] == (
        boundary.isoformat()
    )
    assert runner._last_actual_window["closed_candle_only"] is True
    assert runner._last_actual_window["no_lookahead"] is True
    economics = runner._last_actual_window["execution_economics"]
    assert economics["contract"] == "DETERMINISTIC_HYBRID"
    assert economics["historical_price_side"] == "UNKNOWN_SINGLE_PRICE"
    assert set(economics["parity_claims"].values()) == {False}
    provenance = runner._last_actual_window[
        "instrument_specification_provenance"
    ]
    assert provenance["provenance"] == "CURRENT_SNAPSHOT_ASSUMPTION"
    assert provenance["historical_specification_verified"] is False
    assert provenance["contract_size"] is None
    account = runner._last_actual_window["research_account_economics"]
    assert account["risk_capital_source"] == "REALIZED_SIMULATED_BALANCE"
    assert account["mark_to_market_equity_modeled"] is False


def test_runner_without_end_time_still_forwards_shared_window_contract() -> None:
    class LegacyLoader:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def load(self, **kwargs: object) -> SimpleNamespace:
            self.calls.append(dict(kwargs))
            return _context()

    runner = BacktestRunner(BacktestConfig())
    loader = LegacyLoader()
    runner.loader = loader
    runner.engine = _Engine()

    runner.run(
        symbol="XAUUSD",
        timeframe=mt5.TIMEFRAME_M5,
        bars=5_000,
    )

    assert loader.calls == [
        {
            "symbol": "XAUUSD",
            "bars": 5_000,
            "end_time": None,
            "warmup_bars": 200,
            "analysis_window_bars": 500,
        }
    ]
    assert runner._last_requested_end_time is None
    assert runner._last_actual_window["requested_end_time"] is None


def test_window_metadata_records_actual_timeframe_ranges() -> None:
    runner = BacktestRunner(BacktestConfig())
    runner.loader = SimpleNamespace(load=lambda **kwargs: _context())
    runner.engine = _Engine()

    runner.run(
        symbol="XAUUSD",
        timeframe=mt5.TIMEFRAME_M5,
        bars=100,
        end_time=datetime(2026, 4, 9, 12, 0, tzinfo=UTC),
    )

    actual = runner._last_actual_window["actual"]
    assert actual["m5"]["count"] == 2
    assert actual["m15"]["count"] == 2
    assert actual["h1"]["count"] == 2
    assert actual["h4"]["count"] == 2
    assert actual["m15"]["first_timestamp"] == (
        datetime(2026, 4, 9, 8, 0, tzinfo=UTC).isoformat()
    )
    assert runner._last_actual_window["decision_clock"] == "M5"
    assert runner._last_actual_window["simulation_clock"] == "M15_COMPLETED"
    costs = runner._last_actual_window["execution_cost_assumptions"]
    assert costs["spread_source"] == "PINNED_EXPLICIT_ASSUMPTION"
    assert costs["historical_spread_field_used"] is False


def test_runner_rejects_m15_decision_clock() -> None:
    runner = BacktestRunner(BacktestConfig())

    try:
        runner.run(symbol="XAUUSD", timeframe=mt5.TIMEFRAME_M15, bars=100)
    except ValueError as error:
        assert "TIMEFRAME_M5" in str(error)
    else:
        raise AssertionError("M15 decision clock must fail closed")
