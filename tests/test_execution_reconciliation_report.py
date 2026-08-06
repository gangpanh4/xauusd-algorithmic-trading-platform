from __future__ import annotations

import json
from datetime import UTC, datetime

from core.live_trading.execution_reconciliation_report import (
    ExecutionReconciliationReporter,
)


def _row() -> dict[str, object]:
    return {
        "recorded_at": datetime(
            2026,
            8,
            7,
            2,
            0,
            tzinfo=UTC,
        ).isoformat(),
        "intent_key": "a" * 64,
        "broker_comment": "xau:" + "a" * 16,
        "magic_number": 20260722,
        "intent_status_before": "PREPARED",
        "intent_status_after": "PREPARED",
        "reconciliation_disposition": "UNRESOLVED_NO_EVIDENCE",
        "matching_order_ticket": None,
        "matching_deal_tickets": [],
        "active_order_match_count": 0,
        "historical_order_match_count": 0,
        "execution_deal_match_count": 0,
        "open_position_match_count": 0,
        "startup_allowed": False,
        "automatic_resubmission_attempted": False,
        "live_execution_enabled": False,
        "shadow_only": True,
        "trade_executed": False,
        "failure_reason": "",
    }


def test_reporter_accepts_safe_row(tmp_path) -> None:
    input_path = tmp_path / "audit.jsonl"
    input_path.write_text(json.dumps(_row()) + "\n", encoding="utf-8")
    reporter = ExecutionReconciliationReporter(
        input_path=input_path,
        output_directory=tmp_path / "out",
    )
    summary = reporter.calculate()
    assert summary["validation_passed"] is True
    assert summary["startup_blocked_count"] == 1


def test_reporter_detects_unsafe_semantics(tmp_path) -> None:
    row = _row()
    row["trade_executed"] = True
    input_path = tmp_path / "audit.jsonl"
    input_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    reporter = ExecutionReconciliationReporter(
        input_path=input_path,
        output_directory=tmp_path / "out",
    )
    summary = reporter.calculate()
    assert summary["validation_passed"] is False
    assert summary["semantic_violation_count"] == 1
