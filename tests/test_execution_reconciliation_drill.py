from __future__ import annotations

import json
from datetime import UTC, datetime

from core.live_trading.execution_reconciliation_drill import (
    build_default_restart_reconciliation_drills,
    export_restart_reconciliation_drill_summary,
    run_restart_reconciliation_drills,
)

NOW = datetime(2026, 8, 7, 3, 0, tzinfo=UTC)


def test_default_restart_drill_matrix_passes() -> None:
    cases = build_default_restart_reconciliation_drills(
        observed_at=NOW,
    )
    summary = run_restart_reconciliation_drills(
        cases,
        as_of=NOW.replace(minute=5),
        generated_at=NOW,
    )

    assert summary.total_cases == 8
    assert summary.passed_cases == 8
    assert summary.failed_cases == 0
    assert summary.fail_closed_cases == 2
    assert summary.validation_passed is True
    assert summary.automatic_resubmission_attempted is False
    assert summary.trade_executed is False
    assert summary.live_execution_enabled is False


def test_default_drills_cover_required_restart_outcomes() -> None:
    summary = run_restart_reconciliation_drills(
        build_default_restart_reconciliation_drills(observed_at=NOW),
        as_of=NOW.replace(minute=5),
        generated_at=NOW,
    )
    dispositions = {result.disposition for result in summary.results}

    assert "UNRESOLVED_NO_EVIDENCE" in dispositions
    assert "ACTIVE_ORDER_CONFIRMED" in dispositions
    assert "FILLED_CONFIRMED" in dispositions
    assert "CANCELLED_CONFIRMED" in dispositions
    assert "REJECTED_CONFIRMED" in dispositions
    assert "FAILED_CLOSED" in dispositions


def test_drill_export_is_deterministic_and_non_authoritative(tmp_path) -> None:
    summary = run_restart_reconciliation_drills(
        build_default_restart_reconciliation_drills(observed_at=NOW),
        as_of=NOW.replace(minute=5),
        generated_at=NOW,
    )
    target = export_restart_reconciliation_drill_summary(
        tmp_path / "restart_drills.json",
        summary,
    )
    payload = json.loads(target.read_text(encoding="utf-8"))

    assert payload["validation_passed"] is True
    assert payload["automatic_resubmission_attempted"] is False
    assert payload["trade_executed"] is False
    assert payload["live_execution_enabled"] is False
    assert len(payload["results"]) == 8
