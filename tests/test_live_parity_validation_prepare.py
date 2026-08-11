from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

import core.live_trading.parity_validation_prepare as prepare_module

NOW = datetime(2026, 8, 10, 22, 0, tzinfo=UTC)


def test_main_prepares_only_from_safe_disabled_controls(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def prepare(*, config, now):
        captured["config"] = config
        captured["now"] = now
        return SimpleNamespace(
            schema_version=1,
            validated_at=NOW,
            parity_evidence_path="runtime/live_parity_evidence.jsonl",
            parity_evidence_sha256="a" * 64,
            parity_evidence_size_bytes=123,
            source_commit="b" * 40,
            analytical_contract_version="M5_ANALYTICAL_CONTRACT_V1",
            history_contract_version=(
                "SOURCE_M5_M15_H1_H4_DERIVE_D1_W1_FROM_H4_V1"
            ),
            pipeline_config_fingerprint="c" * 64,
            total_evidence_count=4,
            compatible_evidence_count=4,
            parity_pass_count=4,
            validation_passed=True,
            live_execution_enabled=False,
            trade_executed=False,
        )

    monkeypatch.setattr(
        prepare_module,
        "prepare_parity_validation_attestation",
        prepare,
    )

    assert prepare_module.main() == 0
    config = captured["config"]
    assert config.live_execution_enabled is False
    assert config.demo_execution_approved is False
    assert config.execution_kill_switch_enabled is True
    assert config.parity_recording_enabled is False

    output = json.loads(capsys.readouterr().out)
    assert output["validation_passed"] is True
    assert output["trade_executed"] is False


def test_main_fails_closed_when_attestation_cannot_be_prepared(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(*, config, now):
        raise prepare_module.ParityValidationAttestationError("injected failure")

    monkeypatch.setattr(
        prepare_module,
        "prepare_parity_validation_attestation",
        fail,
    )

    assert prepare_module.main() == 2
    assert "failed closed" in capsys.readouterr().out


def test_preparation_module_has_no_mt5_or_broker_mutation_surface() -> None:
    source = inspect.getsource(prepare_module)

    assert "MetaTrader5" not in source
    assert "order_send" not in source
    assert "order_check" not in source
