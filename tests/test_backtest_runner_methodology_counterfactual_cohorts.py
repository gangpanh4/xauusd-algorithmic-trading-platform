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


def _runner(tmp_path) -> BacktestRunner:
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
        "requested_end_time": "2026-07-27T23:59:00+00:00"
    }
    return runner


def test_generate_reports_exports_counterfactual_cohort_artifacts(
    tmp_path,
    capsys,
) -> None:
    runner = _runner(tmp_path)

    runner.generate_reports(_empty_result())

    csv_path = tmp_path / "methodology_counterfactual_cohorts.csv"
    json_path = tmp_path / "methodology_counterfactual_cohorts.json"
    assert csv_path.exists()
    assert json_path.exists()

    with csv_path.open(newline="", encoding="utf-8") as file:
        assert list(csv.DictReader(file))
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["window_metadata"] == runner._last_actual_window
    assert payload["trade_authority"] is False
    assert payload["methodology_rules_modified"] is False
    capsys.readouterr()


def test_counterfactual_outputs_are_additive(tmp_path, capsys) -> None:
    runner = _runner(tmp_path)

    runner.generate_reports(_empty_result())

    expected = {
        "methodology_condition_outcome_attribution.json",
        "methodology_counterfactual_cohorts.csv",
        "methodology_counterfactual_cohorts.json",
    }
    assert expected.issubset(
        {path.name for path in tmp_path.iterdir()}
    )
    capsys.readouterr()
