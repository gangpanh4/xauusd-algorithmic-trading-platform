from __future__ import annotations

import csv
import json
from types import SimpleNamespace

from core.backtesting.config import BacktestConfig
from core.backtesting.models import BacktestResult
from core.backtesting.runner import BacktestRunner


def _empty_result() -> BacktestResult:
    return BacktestResult(
        total_trades=0,
        winning_trades=0,
        losing_trades=0,
        breakeven_trades=0,
        net_profit=0.0,
        win_rate=0.0,
        max_drawdown=0.0,
    )


def test_generate_reports_exports_condition_outcome_attribution(
    tmp_path,
    capsys,
) -> None:
    runner = BacktestRunner(
        BacktestConfig(output_directory=str(tmp_path)),
    )
    runner.engine = SimpleNamespace(
        observation_audits=(),
        methodology_observations=(),
        methodology_summary=lambda: {},
    )
    runner._last_m5_bars = ()
    runner._last_actual_window = {
        "requested_end_time": "2026-04-09T23:59:00+00:00"
    }

    runner.generate_reports(_empty_result())

    csv_path = (
        tmp_path / "methodology_condition_outcome_attribution.csv"
    )
    json_path = (
        tmp_path / "methodology_condition_outcome_attribution.json"
    )
    assert csv_path.exists()
    assert json_path.exists()

    with csv_path.open(newline="", encoding="utf-8") as file:
        assert list(csv.DictReader(file)) == []

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["window_metadata"] == runner._last_actual_window
    assert payload["observational_only"] is True
    assert payload["trade_authority"] is False
    capsys.readouterr()


def test_attribution_outputs_are_additive(tmp_path, capsys) -> None:
    runner = BacktestRunner(
        BacktestConfig(output_directory=str(tmp_path)),
    )
    runner.engine = SimpleNamespace(
        observation_audits=(),
        methodology_observations=(),
        methodology_summary=lambda: {},
    )
    runner._last_m5_bars = ()

    runner.generate_reports(_empty_result())

    expected = {
        "methodology_outcomes.csv",
        "methodology_outcome_integrity.json",
        "methodology_outcome_stability.json",
        "methodology_condition_outcome_attribution.csv",
        "methodology_condition_outcome_attribution.json",
    }
    assert expected.issubset(
        {path.name for path in tmp_path.iterdir()}
    )
    capsys.readouterr()
