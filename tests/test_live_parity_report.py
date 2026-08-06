from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from core.live_trading.parity_report import LiveParityReporter
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
