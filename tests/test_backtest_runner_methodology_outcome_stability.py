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
    return runner


def test_generate_reports_exports_stability_artifacts(
    tmp_path,
    capsys,
) -> None:
    runner = _runner(tmp_path)

    runner.generate_reports(_empty_result())

    csv_path = tmp_path / "methodology_outcome_stability.csv"
    json_path = tmp_path / "methodology_outcome_stability.json"
    assert csv_path.exists()
    assert json_path.exists()

    with csv_path.open(newline="", encoding="utf-8") as file:
        assert list(csv.DictReader(file)) == []

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["total_unique_observations"] == 0
    assert payload["fold_count"] == 5
    assert payload["observational_only"] is True
    assert payload["trade_authority"] is False
    capsys.readouterr()


def test_stability_outputs_are_additive_to_existing_research(
    tmp_path,
    capsys,
) -> None:
    runner = _runner(tmp_path)

    runner.generate_reports(_empty_result())

    expected = {
        "methodology_outcomes.csv",
        "methodology_outcome_summary.json",
        "methodology_outcome_integrity.json",
        "methodology_outcome_comparison.csv",
        "methodology_outcome_comparison.json",
        "methodology_outcome_stability.csv",
        "methodology_outcome_stability.json",
    }
    assert expected.issubset(
        {path.name for path in tmp_path.iterdir()}
    )
    capsys.readouterr()
