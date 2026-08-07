from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from core.live_trading.config import LiveTradingConfig
from core.live_trading.connected_reconciliation_probe import (
    ConnectedReconciliationProbeResult,
)
from core.live_trading.sustained_reconciliation_monitor import (
    SustainedReconciliationMonitorError,
    build_monitoring_sample,
    run_sustained_monitoring,
    summarize_monitoring_samples,
)

NOW = datetime(2026, 8, 7, 5, 0, tzinfo=UTC)


def _result() -> ConnectedReconciliationProbeResult:
    return ConnectedReconciliationProbeResult(
        recorded_at=NOW,
        symbol="XAUUSD",
        account_login=123456,
        account_server="MetaQuotes-Demo",
        account_trade_mode=0,
        demo_account_confirmed=True,
        live_execution_enabled=False,
        shadow_only=True,
        order_submission_attempted=False,
        trade_executed=False,
        persisted_intent_present=False,
        persisted_intent_key=None,
        persisted_intent_status_before=None,
        reconciled_intent_status=None,
        reconciliation_disposition="NO_PERSISTED_INTENT",
        reconciliation_reason="read-only",
        matching_order_ticket=None,
        matching_deal_tickets=(),
        active_order_count=0,
        historical_order_count=0,
        execution_deal_count=0,
        open_position_count=0,
        validation_passed=True,
    )


def test_monitoring_sample_detects_state_change() -> None:
    previous = _result()
    current = replace(previous, active_order_count=1)
    sample = build_monitoring_sample(
        sequence=2,
        result=current,
        previous=previous,
        captured_at=NOW,
    )
    assert sample.state_changed is True
    assert sample.change_fields == ("active_order_count",)
    assert sample.alert_required is False


def test_monitoring_sample_alerts_on_account_change() -> None:
    previous = _result()
    current = replace(previous, account_login=999999)
    sample = build_monitoring_sample(
        sequence=2,
        result=current,
        previous=previous,
        captured_at=NOW,
    )
    assert sample.alert_required is True
    assert "ACCOUNT_IDENTITY_CHANGED" in sample.alert_reasons


def test_summary_passes_for_consistent_read_only_samples() -> None:
    first = build_monitoring_sample(
        sequence=1,
        result=_result(),
        previous=None,
        captured_at=NOW,
    )
    second = build_monitoring_sample(
        sequence=2,
        result=_result(),
        previous=_result(),
        captured_at=NOW,
    )
    summary = summarize_monitoring_samples(
        (first, second),
        generated_at=NOW,
    )
    assert summary.validation_passed is True
    assert summary.sample_count == 2
    assert summary.alert_count == 0
    assert summary.live_execution_enabled is False
    assert summary.trade_executed is False


def test_sustained_monitoring_appends_and_exports(tmp_path) -> None:
    result = _result()
    calls = 0

    def runner(**kwargs):
        nonlocal calls
        calls += 1
        return result

    summary = run_sustained_monitoring(
        config=LiveTradingConfig(live_execution_enabled=False),
        iterations=3,
        interval_seconds=0.0,
        lookback_hours=24,
        evidence_path=tmp_path / "monitor.jsonl",
        summary_path=tmp_path / "summary.json",
        probe_runner=runner,
        sleeper=lambda seconds: None,
    )
    assert calls == 3
    assert summary.validation_passed is True
    assert len((tmp_path / "monitor.jsonl").read_text().splitlines()) == 3
    assert (tmp_path / "summary.json").is_file()


def test_sustained_monitoring_fails_closed_on_alert(tmp_path) -> None:
    unsafe = replace(_result(), trade_executed=True)

    with pytest.raises(
        SustainedReconciliationMonitorError,
        match="TRADE_EXECUTED",
    ):
        run_sustained_monitoring(
            config=LiveTradingConfig(live_execution_enabled=False),
            iterations=1,
            interval_seconds=0.0,
            lookback_hours=24,
            evidence_path=tmp_path / "monitor.jsonl",
            summary_path=tmp_path / "summary.json",
            probe_runner=lambda **kwargs: unsafe,
            sleeper=lambda seconds: None,
        )
