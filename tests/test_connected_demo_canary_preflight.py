from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.live_trading.config import LiveTradingConfig
from core.live_trading.connected_demo_canary_preflight import (
    ConnectedDemoCanaryPreflightError,
    collect_connected_demo_canary_preflight_evidence,
)
from core.live_trading.connected_reconciliation_probe import (
    ConnectedReconciliationProbeResult,
)
from core.live_trading.partial_fill_store import (
    PartialFillStateStore,
    PersistedPartialFill,
)
from core.mt5_execution.models import SymbolInfo

NOW = datetime(2026, 8, 8, 3, 0, tzinfo=UTC)


def _config(tmp_path: Path) -> LiveTradingConfig:
    return LiveTradingConfig(
        live_execution_enabled=False,
        demo_execution_approved=False,
        execution_kill_switch_enabled=True,
        partial_fill_state_path=tmp_path / "partial.json",
        execution_intent_state_path=tmp_path / "intent.json",
    )


def _probe(**overrides) -> ConnectedReconciliationProbeResult:
    values = {
        "recorded_at": NOW,
        "symbol": "XAUUSD",
        "account_login": 123456,
        "account_server": "MetaQuotes-Demo",
        "account_trade_mode": 0,
        "demo_account_confirmed": True,
        "live_execution_enabled": False,
        "shadow_only": True,
        "order_submission_attempted": False,
        "trade_executed": False,
        "persisted_intent_present": False,
        "persisted_intent_key": None,
        "persisted_intent_status_before": None,
        "reconciled_intent_status": None,
        "reconciliation_disposition": "NO_PERSISTED_INTENT",
        "reconciliation_reason": "clear",
        "matching_order_ticket": None,
        "matching_deal_tickets": (),
        "active_order_count": 0,
        "historical_order_count": 0,
        "execution_deal_count": 0,
        "open_position_count": 0,
        "validation_passed": True,
    }
    values.update(overrides)
    return ConnectedReconciliationProbeResult(**values)


def _symbol() -> SymbolInfo:
    return SymbolInfo(
        name="XAUUSD",
        digits=2,
        point=0.01,
        spread=20,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        trade_allowed=True,
        tick_size=0.01,
        minimum_stop_distance=0.1,
        filling_mode_flags=1,
        trade_execution_mode=2,
    )


def test_clean_connected_preflight_passes_without_execution(tmp_path: Path) -> None:
    evidence = collect_connected_demo_canary_preflight_evidence(
        config=_config(tmp_path),
        lookback_hours=24,
        as_of=NOW,
        probe_runner=lambda **kwargs: _probe(),
        symbol_reader=lambda symbol: _symbol(),
    )

    assert evidence.validation_passed is True
    assert evidence.demo_account_confirmed is True
    assert evidence.reconciliation_clear is True
    assert evidence.active_order_count == 0
    assert evidence.open_position_count == 0
    assert evidence.order_submission_attempted is False
    assert evidence.authorization_consumed is False
    assert evidence.trade_executed is False
    assert evidence.live_execution_enabled is False
    assert evidence.demo_execution_approved is False
    assert evidence.execution_kill_switch_enabled is True


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("active_order_count", 1, "Active broker orders exist."),
        ("open_position_count", 1, "Open broker positions exist."),
        (
            "reconciliation_disposition",
            "FAILED_CLOSED",
            "Execution-intent reconciliation is not clear.",
        ),
    ],
)
def test_connected_preflight_fails_closed_on_broker_state(
    tmp_path: Path,
    field: str,
    value: object,
    reason: str,
) -> None:
    evidence = collect_connected_demo_canary_preflight_evidence(
        config=_config(tmp_path),
        as_of=NOW,
        probe_runner=lambda **kwargs: _probe(**{field: value}),
        symbol_reader=lambda symbol: _symbol(),
    )

    assert evidence.validation_passed is False
    assert reason in evidence.reasons
    assert evidence.order_submission_attempted is False
    assert evidence.trade_executed is False


def test_connected_preflight_detects_persisted_partial_fill(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    PartialFillStateStore(config.partial_fill_state_path).save(
        PersistedPartialFill(
            symbol="XAUUSD",
            ticket=77,
            requested_volume=0.01,
            executed_volume=0.004,
            remaining_volume=0.006,
            created_at=NOW,
        )
    )

    evidence = collect_connected_demo_canary_preflight_evidence(
        config=config,
        as_of=NOW,
        probe_runner=lambda **kwargs: _probe(),
        symbol_reader=lambda symbol: _symbol(),
    )

    assert evidence.validation_passed is False
    assert evidence.unresolved_partial_fill is True
    assert evidence.unresolved_partial_ticket == 77


def test_connected_preflight_requires_safe_execution_flags(
    tmp_path: Path,
) -> None:
    config = LiveTradingConfig(
        live_execution_enabled=True,
        demo_execution_approved=False,
        execution_kill_switch_enabled=True,
        partial_fill_state_path=tmp_path / "partial.json",
        execution_intent_state_path=tmp_path / "intent.json",
    )

    with pytest.raises(
        ConnectedDemoCanaryPreflightError,
        match="live_execution_enabled=False",
    ):
        collect_connected_demo_canary_preflight_evidence(
            config=config,
            as_of=NOW,
            probe_runner=lambda **kwargs: _probe(),
            symbol_reader=lambda symbol: _symbol(),
        )
