from __future__ import annotations

import csv
import json
from types import SimpleNamespace

from core.backtesting.config import BacktestConfig
from core.backtesting.models import BacktestResult
from core.backtesting.runner import BacktestRunner


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


def test_runner_exports_variant_b_shadow_scoring(
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

    runner.generate_reports(_result())

    csv_path = (
        tmp_path / "methodology_variant_b_shadow_scoring.csv"
    )
    json_path = (
        tmp_path / "methodology_variant_b_shadow_scoring.json"
    )
    assert csv_path.exists()
    assert json_path.exists()
    with csv_path.open(newline="", encoding="utf-8") as file:
        assert list(csv.DictReader(file)) == []
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["variant"] == (
        "VARIANT_B_BEARISH_EXCLUDE_COMPATIBLE_SWEEP"
    )
    assert payload["trade_authority"] is False
    assert payload["active_pipeline_modified"] is False
    capsys.readouterr()
