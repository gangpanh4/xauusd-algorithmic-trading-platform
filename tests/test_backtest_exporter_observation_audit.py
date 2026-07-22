from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta

import pytest

from core.backtesting.exporter import BacktestExporter
from core.trading_pipeline.models import (
    PipelineDisposition,
    PipelineObservationAudit,
    PipelineStage,
)


def _rejected(timestamp: datetime, code: str, stage: PipelineStage) -> PipelineObservationAudit:
    return PipelineObservationAudit(
        timestamp=timestamp,
        disposition=PipelineDisposition.REJECTED,
        stage_reached=stage,
        rejection_stage=stage,
        reason_code=code,
        reason=f"Rejected at {stage.value}",
        regime_confirmed=stage is not PipelineStage.REGIME,
        feature_count=2 if stage.value >= PipelineStage.FEATURES.value else 0,
    )


def _accepted(timestamp: datetime) -> PipelineObservationAudit:
    return PipelineObservationAudit(
        timestamp=timestamp,
        disposition=PipelineDisposition.ACCEPTED,
        stage_reached=PipelineStage.APPROVED,
        regime_confirmed=True,
        bos_present=True,
        liquidity_present=True,
        feature_count=8,
        probability_calculated=True,
        probability_accepted=True,
        probability_value=0.72,
        trade_quality_calculated=True,
        trade_quality_approved=True,
        trade_quality_score=0.68,
        confluence_available=True,
        confluence_approved=True,
        confluence_score=0.75,
        signal_generated=True,
        risk_approved=True,
    )


def test_exports_zero_observation_files(tmp_path) -> None:
    exporter = BacktestExporter(tmp_path)

    csv_path = exporter.export_observation_audit(())
    json_path = exporter.export_rejection_summary(())

    with csv_path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert rows == []

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload == {
        "accepted_observations": 0,
        "disposition_counts": {},
        "reason_code_counts": {},
        "rejected_observations": 0,
        "rejection_stage_counts": {},
        "total_observations": 0,
    }


def test_exports_complete_audit_rows_and_summary(tmp_path) -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    audits = (
        _rejected(start, "REGIME_UNCONFIRMED", PipelineStage.REGIME),
        _rejected(
            start + timedelta(minutes=15),
            "PROBABILITY_REJECTED",
            PipelineStage.PROBABILITY,
        ),
        _accepted(start + timedelta(minutes=30)),
    )
    exporter = BacktestExporter(tmp_path)

    csv_path = exporter.export_observation_audit(audits)
    json_path = exporter.export_rejection_summary(audits)

    with csv_path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 3
    assert rows[0]["Observation Number"] == "1"
    assert rows[0]["Reason Code"] == "REGIME_UNCONFIRMED"
    assert rows[2]["Disposition"] == "ACCEPTED"
    assert rows[2]["Probability Value"] == "0.72"
    assert rows[2]["Risk Approved"] == "True"

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["total_observations"] == 3
    assert payload["accepted_observations"] == 1
    assert payload["rejected_observations"] == 2
    assert payload["reason_code_counts"] == {
        "APPROVED": 1,
        "PROBABILITY_REJECTED": 1,
        "REGIME_UNCONFIRMED": 1,
    }
    assert payload["rejection_stage_counts"] == {
        "APPROVED": 1,
        "PROBABILITY": 1,
        "REGIME": 1,
    }


def test_rejects_non_audit_values(tmp_path) -> None:
    exporter = BacktestExporter(tmp_path)
    with pytest.raises(TypeError):
        exporter.export_observation_audit([object()])  # type: ignore[list-item]


def test_rejects_duplicate_or_out_of_order_timestamps(tmp_path) -> None:
    exporter = BacktestExporter(tmp_path)
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    audits = (
        _rejected(timestamp, "REGIME_UNCONFIRMED", PipelineStage.REGIME),
        _rejected(timestamp, "REGIME_UNCONFIRMED", PipelineStage.REGIME),
    )
    with pytest.raises(ValueError, match="strictly increasing"):
        exporter.export_rejection_summary(audits)
