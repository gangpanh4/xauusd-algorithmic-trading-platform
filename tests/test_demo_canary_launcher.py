from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import core.live_trading.demo_canary_launcher as launcher
from core.live_trading.config import LiveTradingConfig
from core.live_trading.demo_execution_authorization import (
    DemoExecutionAuthorization,
)

NOW = datetime(2026, 8, 10, 7, 0, tzinfo=UTC)


def _authorization(**overrides: object) -> DemoExecutionAuthorization:
    values: dict[str, object] = {
        "schema_version": 1,
        "authorization_id": "one-shot-canary",
        "issued_at": NOW - timedelta(minutes=1),
        "expires_at": NOW + timedelta(minutes=10),
        "account_login": 123456,
        "account_server": "MetaQuotes-Demo",
        "symbol": "XAUUSD",
        "maximum_volume": 0.01,
        "maximum_submissions": 1,
        "demo_only": True,
        "one_shot": True,
        "acknowledgement": "I AUTHORIZE ONE DEMO ORDER",
        "consumed_at": None,
        "consumed_intent_key": None,
    }
    values.update(overrides)
    return DemoExecutionAuthorization(**values)  # type: ignore[arg-type]


def test_active_config_is_process_local_one_shot_canary() -> None:
    safe = LiveTradingConfig()
    active = launcher._build_active_canary_config(
        safe,
        _authorization(),
    )

    assert safe.live_execution_enabled is False
    assert safe.demo_execution_approved is False
    assert safe.execution_kill_switch_enabled is True

    assert active.live_execution_enabled is True
    assert active.demo_execution_approved is True
    assert active.execution_kill_switch_enabled is False
    assert active.symbol == "XAUUSD"
    assert active.approved_account_login == 123456
    assert active.approved_account_server == "MetaQuotes-Demo"
    assert active.maximum_order_submissions_per_session == 1
    assert active.execution.allowed_order_volume == pytest.approx(0.01)


@pytest.mark.parametrize(
    "overrides",
    [
        {"symbol": "EURUSD"},
        {"maximum_volume": 0.02},
        {"maximum_submissions": 2},
        {"one_shot": False},
        {"demo_only": False},
        {"consumed_at": NOW},
    ],
)
def test_initial_authorization_refuses_non_canary_scope(
    overrides: dict[str, object],
) -> None:
    with pytest.raises((launcher.DemoCanaryLauncherError, RuntimeError)):
        launcher._validate_initial_authorization(
            _authorization(**overrides),
            now=NOW,
        )


def test_expired_authorization_is_rejected_before_mt5_connection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    config = LiveTradingConfig(
        demo_authorization_path=tmp_path / "authorization.json",
        parity_evidence_path=tmp_path / "parity.jsonl",
    )
    expired = _authorization(
        issued_at=NOW - timedelta(minutes=10),
        expires_at=NOW - timedelta(seconds=1),
    )
    config.demo_authorization_path.write_text(
        json.dumps(expired.to_payload(), sort_keys=True),
        encoding="utf-8",
    )
    monkeypatch.setattr(launcher, "_utc_now", lambda: NOW)
    initialize = Mock(return_value=True)
    monkeypatch.setattr(launcher.mt5, "initialize", initialize)

    with pytest.raises(RuntimeError, match="expired"):
        launcher._run_one_shot_demo_canary(config)

    initialize.assert_not_called()
    loaded = json.loads(
        config.demo_authorization_path.read_text(encoding="utf-8")
    )
    assert loaded["consumed_at"] is None
    assert loaded["consumed_intent_key"] is None


def test_parity_is_established_only_from_production_report(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    config = LiveTradingConfig(
        parity_evidence_path=tmp_path / "parity.jsonl",
        parity_report_directory=tmp_path / "out",
    )
    engine = SimpleNamespace(record_parity_validation_passed=Mock())

    class PassingReporter:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

        def calculate(self) -> dict[str, object]:
            return {"validation_passed": True}

    monkeypatch.setattr(launcher, "LiveParityReporter", PassingReporter)

    launcher._establish_parity_validation(engine, config)  # type: ignore[arg-type]

    engine.record_parity_validation_passed.assert_called_once_with()


def test_failed_parity_never_records_runtime_validation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    config = LiveTradingConfig(
        parity_evidence_path=tmp_path / "parity.jsonl",
        parity_report_directory=tmp_path / "out",
    )
    engine = SimpleNamespace(record_parity_validation_passed=Mock())

    class FailingReporter:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

        def calculate(self) -> dict[str, object]:
            return {"validation_passed": False}

    monkeypatch.setattr(launcher, "LiveParityReporter", FailingReporter)

    with pytest.raises(
        launcher.DemoCanaryLauncherError,
        match="parity validation did not pass",
    ):
        launcher._establish_parity_validation(engine, config)  # type: ignore[arg-type]

    engine.record_parity_validation_passed.assert_not_called()


def test_preflight_binding_requires_exact_account_and_001_volume() -> None:
    evidence = SimpleNamespace(
        validation_passed=True,
        reasons=(),
        demo_account_confirmed=True,
        symbol="XAUUSD",
        account_login=123456,
        account_server="MetaQuotes-Demo",
        active_order_count=0,
        open_position_count=0,
        unresolved_partial_fill=False,
        reconciliation_clear=True,
        persisted_intent_present=False,
        persisted_intent_status=None,
        authorization_consumed=False,
        symbol_volume_min=0.01,
        symbol_volume_max=100.0,
        symbol_volume_step=0.01,
    )

    launcher._validate_preflight_binding(
        evidence,  # type: ignore[arg-type]
        _authorization(),
    )

    bad_account = SimpleNamespace(**vars(evidence))
    bad_account.account_login = 654321
    with pytest.raises(
        launcher.DemoCanaryLauncherError,
        match="identity",
    ):
        launcher._validate_preflight_binding(
            bad_account,  # type: ignore[arg-type]
            _authorization(),
        )
