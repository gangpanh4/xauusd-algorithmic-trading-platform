from __future__ import annotations

import json
from datetime import UTC, datetime

from core.live_trading.demo_execution_authorization_audit import (
    export_authorization_audit_summary,
    run_demo_execution_authorization_audit,
)

NOW = datetime(2026, 8, 8, 1, 30, tzinfo=UTC)


def test_rejection_audit_matrix_passes(tmp_path) -> None:
    summary = run_demo_execution_authorization_audit(
        tmp_path / "cases",
        now=NOW,
        generated_at=NOW,
    )

    assert summary.total_cases == 20
    assert summary.passed_cases == 20
    assert summary.failed_cases == 0
    assert summary.blocked_cases == 19
    assert summary.broker_submission_count == 1
    assert summary.trade_executed is False
    assert summary.live_broker_used is False
    assert summary.validation_passed is True


def test_every_rejection_case_has_zero_submission_attempts(tmp_path) -> None:
    summary = run_demo_execution_authorization_audit(
        tmp_path / "cases",
        now=NOW,
        generated_at=NOW,
    )

    for result in summary.results:
        if result.name == "valid_one_shot":
            assert result.blocked is False
            assert result.broker_submission_count == 1
            assert result.broker_submission_attempted is True
        else:
            assert result.blocked is True
            assert result.broker_submission_count == 0
            assert result.broker_submission_attempted is False
        assert result.trade_executed is False


def test_rejection_audit_exports_non_live_evidence(tmp_path) -> None:
    summary = run_demo_execution_authorization_audit(
        tmp_path / "cases",
        now=NOW,
        generated_at=NOW,
    )
    output = export_authorization_audit_summary(
        tmp_path / "authorization_rejection_audit.json",
        summary,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["validation_passed"] is True
    assert payload["live_broker_used"] is False
    assert payload["trade_executed"] is False
    assert payload["broker_submission_count"] == 1
    assert len(payload["results"]) == 20
