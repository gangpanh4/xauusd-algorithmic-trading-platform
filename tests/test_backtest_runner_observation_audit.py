from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from types import SimpleNamespace

from core.backtesting.config import BacktestConfig
from core.backtesting.models import BacktestResult
from core.backtesting.runner import BacktestRunner
from core.trading_pipeline.models import (
    PipelineDisposition,
    PipelineObservationAudit,
    PipelineStage,
)


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


def _rejected_audit() -> PipelineObservationAudit:
    return PipelineObservationAudit(
        timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        disposition=PipelineDisposition.REJECTED,
        stage_reached=PipelineStage.PROBABILITY,
        rejection_stage=PipelineStage.PROBABILITY,
        reason_code="PROBABILITY_REJECTED",
        reason="probability below threshold",
        regime_confirmed=True,
        bos_present=True,
        liquidity_present=True,
        feature_count=7,
        probability_calculated=True,
        probability_accepted=False,
        probability_value=0.42,
    )


def _runner(tmp_path, audits: tuple[PipelineObservationAudit, ...]) -> BacktestRunner:
    runner = BacktestRunner(
        BacktestConfig(output_directory=str(tmp_path)),
    )
    runner.engine = SimpleNamespace(observation_audits=audits)
    return runner


def test_generate_reports_exports_empty_observation_artifacts(tmp_path, capsys) -> None:
    runner = _runner(tmp_path, ())

    runner.generate_reports(_empty_result())

    audit_path = tmp_path / "observation_audit.csv"
    summary_path = tmp_path / "rejection_summary.json"
    assert audit_path.exists()
    assert summary_path.exists()

    with audit_path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert rows == []

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["total_observations"] == 0
    assert payload["reason_code_counts"] == {}
    capsys.readouterr()


def test_generate_reports_exports_engine_observation_audits(tmp_path, capsys) -> None:
    audit = _rejected_audit()
    runner = _runner(tmp_path, (audit,))

    runner.generate_reports(_empty_result())

    with (tmp_path / "observation_audit.csv").open(
        newline="", encoding="utf-8"
    ) as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 1
    assert rows[0]["Reason Code"] == "PROBABILITY_REJECTED"
    assert rows[0]["Probability Value"] == "0.42"

    payload = json.loads(
        (tmp_path / "rejection_summary.json").read_text(encoding="utf-8")
    )
    assert payload["total_observations"] == 1
    assert payload["rejected_observations"] == 1
    assert payload["reason_code_counts"] == {"PROBABILITY_REJECTED": 1}
    capsys.readouterr()
