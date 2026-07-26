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
    return runner


def test_generate_reports_exports_empty_methodology_artifacts(
    tmp_path,
    capsys,
) -> None:
    runner = _runner(tmp_path)

    runner.generate_reports(_empty_result())

    observations_path = tmp_path / "methodology_observations.csv"
    summary_path = tmp_path / "methodology_summary.json"
    assert observations_path.exists()
    assert summary_path.exists()

    with observations_path.open(newline="", encoding="utf-8") as file:
        assert list(csv.DictReader(file)) == []

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["total_observations"] == 0
    assert payload["status_counts"] == {}
    assert payload["observational_only"] is True
    assert payload["trade_authority"] is False
    capsys.readouterr()


def test_generate_reports_preserves_legacy_engine_without_methodology_access(
    tmp_path,
    capsys,
) -> None:
    runner = BacktestRunner(
        BacktestConfig(output_directory=str(tmp_path)),
    )
    runner.engine = SimpleNamespace(observation_audits=())

    runner.generate_reports(_empty_result())

    payload = json.loads(
        (tmp_path / "methodology_summary.json").read_text(encoding="utf-8")
    )
    assert payload["total_observations"] == 0
    assert payload["methodologies"]["SMC"]["CONFIRMED"] == 0
    assert payload["methodologies"]["ICT"]["CONFIRMED"] == 0
    capsys.readouterr()
