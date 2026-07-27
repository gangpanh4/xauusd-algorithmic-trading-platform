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


def test_generate_reports_exports_outcome_integrity_artifacts(
    tmp_path,
    capsys,
) -> None:
    runner = _runner(tmp_path)

    runner.generate_reports(_empty_result())

    expected = {
        "methodology_outcome_integrity.json",
        "methodology_outcome_comparison.csv",
        "methodology_outcome_comparison.json",
    }
    assert expected.issubset(
        {path.name for path in tmp_path.iterdir()}
    )

    integrity = json.loads(
        (tmp_path / "methodology_outcome_integrity.json").read_text(
            encoding="utf-8"
        )
    )
    assert integrity["methodology_observation_count"] == 0
    assert integrity["evaluation_count_matches"] is True
    assert integrity["trade_authority"] is False

    with (
        tmp_path / "methodology_outcome_comparison.csv"
    ).open(newline="", encoding="utf-8") as file:
        assert list(csv.DictReader(file)) == []

    comparison = json.loads(
        (tmp_path / "methodology_outcome_comparison.json").read_text(
            encoding="utf-8"
        )
    )
    assert comparison["comparisons"] == []
    assert comparison["observational_only"] is True
    capsys.readouterr()


def test_integrity_reports_are_additive_to_existing_outputs(
    tmp_path,
    capsys,
) -> None:
    runner = _runner(tmp_path)

    runner.generate_reports(_empty_result())

    expected = {
        "methodology_observations.csv",
        "methodology_summary.json",
        "methodology_condition_summary.csv",
        "methodology_condition_summary.json",
        "methodology_outcomes.csv",
        "methodology_outcome_summary.json",
        "methodology_outcome_integrity.json",
        "methodology_outcome_comparison.csv",
        "methodology_outcome_comparison.json",
    }
    assert expected.issubset(
        {path.name for path in tmp_path.iterdir()}
    )
    capsys.readouterr()
