from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from core.data.models import MarketBar
from core.live_trading.parity_evidence import LiveParityEvidence
from core.live_trading.parity_report import LiveParityReporter
from core.multi_timeframe.enums import Timeframe
from core.trading_pipeline.models import (
    PipelineDisposition,
    PipelineObservationAudit,
    PipelineStage,
)


def _audit() -> PipelineObservationAudit:
    return PipelineObservationAudit(
        timestamp=datetime(2026, 8, 6, 10, 0, tzinfo=UTC),
        disposition=PipelineDisposition.REJECTED,
        stage_reached=PipelineStage.RISK,
        rejection_stage=PipelineStage.PROBABILITY,
        reason_code="PROBABILITY_REJECTED",
        reason="Probability policy rejected the observation.",
        regime_confirmed=True,
        feature_count=31,
        probability_calculated=True,
        probability_accepted=False,
        probability_value=0.5713071017561531,
        trade_quality_calculated=True,
        trade_quality_approved=False,
        trade_quality_score=0.32673,
        confluence_available=True,
        confluence_approved=False,
        confluence_score=0.100725,
        signal_generated=False,
        risk_approved=False,
    )


def _bar(timestamp: datetime) -> MarketBar:
    return MarketBar(
        timestamp=timestamp,
        open=4000.0,
        high=4005.0,
        low=3998.0,
        close=4003.0,
        tick_volume=1000,
    )


def _evidence() -> LiveParityEvidence:
    audit = _audit()
    histories = {
        timeframe: (
            _bar(audit.timestamp - timedelta(minutes=5)),
            _bar(audit.timestamp),
        )
        for timeframe in Timeframe
    }
    return LiveParityEvidence(
        captured_at=audit.timestamp + timedelta(minutes=5),
        observation_timestamp=audit.timestamp,
        symbol="XAUUSD",
        bars_by_timeframe=histories,
        account_balance=10_000.0,
        stop_loss_distance=0.01,
        pip_value=0.1,
        tick_size=0.01,
        lot_step=0.01,
        minimum_lot=0.01,
        maximum_lot=100.0,
        expected_audit=audit,
    )


def test_compare_audits_accepts_exact_match() -> None:
    audit = _audit()

    assert LiveParityReporter.compare_audits(audit, audit) == []


def test_compare_audits_names_controlled_mismatch() -> None:
    live = _audit()
    replay = replace(live, probability_value=0.6)

    mismatches = LiveParityReporter.compare_audits(live, replay)

    assert mismatches == [
        {
            "field": "probability_value",
            "live_value": live.probability_value,
            "replay_value": 0.6,
        }
    ]


def test_empty_parity_input_fails_closed(tmp_path) -> None:
    reporter = LiveParityReporter(
        input_path=tmp_path / "missing.jsonl",
        output_directory=tmp_path / "output",
    )

    report = reporter.calculate()

    assert report["total_evidence_count"] == 0
    assert report["validation_passed"] is False
    assert report["live_execution_enabled"] is False
    assert report["trade_executed"] is False


def test_corrupted_json_fails_closed(tmp_path) -> None:
    path = tmp_path / "parity.jsonl"
    path.write_text("{not-json}\n", encoding="utf-8")
    reporter = LiveParityReporter(
        input_path=path,
        output_directory=tmp_path / "output",
    )

    report = reporter.calculate()

    assert report["total_evidence_count"] == 1
    assert report["parity_fail_count"] == 1
    assert report["parse_error_count"] == 1
    assert report["validation_passed"] is False
    assert report["results"][0]["mismatches"][0]["field"] == "evidence"


def test_partial_row_does_not_hide_later_valid_evidence(
    tmp_path,
    monkeypatch,
) -> None:
    evidence = _evidence()
    path = tmp_path / "parity.jsonl"
    path.write_text(
        '{"schema_version": 1\n'
        + json.dumps(evidence.to_payload(), sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    reporter = LiveParityReporter(
        input_path=path,
        output_directory=tmp_path / "output",
    )
    monkeypatch.setattr(reporter, "_replay", lambda row: row.expected_audit)

    report = reporter.calculate()

    assert report["total_evidence_count"] == 2
    assert report["parity_pass_count"] == 1
    assert report["parity_fail_count"] == 1
    assert report["parse_error_count"] == 1
    assert report["validation_passed"] is False
    assert report["results"][1]["parity_passed"] is True


def test_altered_audit_field_is_reported_as_divergence(
    tmp_path,
    monkeypatch,
) -> None:
    evidence = _evidence()
    path = tmp_path / "parity.jsonl"
    path.write_text(
        json.dumps(evidence.to_payload(), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    reporter = LiveParityReporter(
        input_path=path,
        output_directory=tmp_path / "output",
    )
    replay = replace(evidence.expected_audit, trade_quality_score=0.9)
    monkeypatch.setattr(reporter, "_replay", lambda row: replay)

    report = reporter.calculate()

    assert report["parity_pass_count"] == 0
    assert report["parity_fail_count"] == 1
    assert report["parse_error_count"] == 0
    assert report["validation_passed"] is False
    assert report["results"][0]["mismatches"] == [
        {
            "field": "trade_quality_score",
            "live_value": evidence.expected_audit.trade_quality_score,
            "replay_value": 0.9,
        }
    ]


def test_missing_timeframe_payload_is_parse_error(tmp_path) -> None:
    evidence = _evidence()
    payload = evidence.to_payload()
    del payload["bars_by_timeframe"]["H4"]
    path = tmp_path / "parity.jsonl"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    reporter = LiveParityReporter(
        input_path=path,
        output_directory=tmp_path / "output",
    )

    report = reporter.calculate()

    assert report["parity_fail_count"] == 1
    assert report["parse_error_count"] == 1
    assert report["validation_passed"] is False


def test_execution_authority_payload_is_parse_error(tmp_path) -> None:
    evidence = _evidence()
    payload = evidence.to_payload()
    payload["live_execution_enabled"] = True
    payload["shadow_only"] = False
    path = tmp_path / "parity.jsonl"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    reporter = LiveParityReporter(
        input_path=path,
        output_directory=tmp_path / "output",
    )

    report = reporter.calculate()

    assert report["parity_fail_count"] == 1
    assert report["parse_error_count"] == 1
    assert report["validation_passed"] is False
    assert report["live_execution_enabled"] is False
    assert report["shadow_only"] is True
    assert report["trade_executed"] is False


def test_replay_never_falls_back_when_target_snapshot_is_incomplete(
    tmp_path,
) -> None:
    reporter = LiveParityReporter(
        input_path=tmp_path / "unused.jsonl",
        output_directory=tmp_path / "output",
    )

    with pytest.raises(RuntimeError, match="complete synchronized M5"):
        reporter._replay(_evidence())
