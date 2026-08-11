from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

import core.live_trading.parity_validation_attestation as attestation_module
from core.live_trading.config import LiveTradingConfig
from core.live_trading.parity_provenance import ParityAnalyticalProvenance

NOW = datetime(2026, 8, 10, 22, 0, tzinfo=UTC)
PROVENANCE = ParityAnalyticalProvenance(
    analytical_contract_version="M5_ANALYTICAL_CONTRACT_V1",
    source_commit="a" * 40,
    pipeline_config_fingerprint="b" * 64,
)


def _config(tmp_path: Path) -> LiveTradingConfig:
    return LiveTradingConfig(
        parity_evidence_path=tmp_path / "live_parity_evidence.jsonl",
        parity_report_directory=tmp_path / "report",
        parity_validation_attestation_path=tmp_path / "attestation.json",
    )


def _passing_report() -> dict[str, object]:
    return {
        "total_evidence_count": 2,
        "compatible_evidence_count": 2,
        "legacy_unversioned_count": 0,
        "provenance_mismatch_count": 0,
        "parity_pass_count": 2,
        "parity_fail_count": 0,
        "parse_error_count": 0,
        "validation_passed": True,
        "live_execution_enabled": False,
        "shadow_only": True,
        "trade_executed": False,
    }


def _install_passing_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        attestation_module.parity_provenance,
        "current_parity_provenance",
        lambda _config: PROVENANCE,
    )

    class PassingReporter:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

        def calculate(self) -> dict[str, object]:
            return _passing_report()

    monkeypatch.setattr(
        attestation_module,
        "LiveParityReporter",
        PassingReporter,
    )


def test_prepare_writes_exact_source_config_and_evidence_binding(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    config.parity_evidence_path.write_bytes(b'{"schema_version":3}\n')
    _install_passing_dependencies(monkeypatch)

    attestation = attestation_module.prepare_parity_validation_attestation(
        config=config,
        now=NOW,
    )

    loaded = attestation_module.load_parity_validation_attestation(
        config.parity_validation_attestation_path
    )
    assert loaded == attestation
    assert loaded.source_commit == "a" * 40
    assert loaded.pipeline_config_fingerprint == "b" * 64
    assert loaded.total_evidence_count == 2
    assert loaded.compatible_evidence_count == 2
    assert loaded.parity_pass_count == 2
    assert loaded.validation_passed is True
    assert loaded.live_execution_enabled is False
    assert loaded.shadow_only is True
    assert loaded.trade_executed is False


def test_failed_full_replay_never_writes_attestation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    config.parity_evidence_path.write_bytes(b'{"schema_version":3}\n')
    monkeypatch.setattr(
        attestation_module.parity_provenance,
        "current_parity_provenance",
        lambda _config: PROVENANCE,
    )

    class FailingReporter:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

        def calculate(self) -> dict[str, object]:
            report = _passing_report()
            report["parity_fail_count"] = 1
            report["parity_pass_count"] = 1
            report["validation_passed"] = False
            return report

    monkeypatch.setattr(
        attestation_module,
        "LiveParityReporter",
        FailingReporter,
    )

    with pytest.raises(
        attestation_module.ParityValidationAttestationError,
        match="did not pass cleanly",
    ):
        attestation_module.prepare_parity_validation_attestation(
            config=config,
            now=NOW,
        )

    assert config.parity_validation_attestation_path.exists() is False


def test_verifier_rejects_changed_evidence_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    config.parity_evidence_path.write_bytes(b'{"schema_version":3}\n')
    _install_passing_dependencies(monkeypatch)
    attestation_module.prepare_parity_validation_attestation(
        config=config,
        now=NOW,
    )

    config.parity_evidence_path.write_bytes(
        b'{"schema_version":3,"changed":true}\n'
    )

    with pytest.raises(
        attestation_module.ParityValidationAttestationError,
        match="evidence bytes changed",
    ):
        attestation_module.verify_parity_validation_attestation(config=config)


def test_verifier_rejects_source_commit_change(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    config.parity_evidence_path.write_bytes(b'{"schema_version":3}\n')
    _install_passing_dependencies(monkeypatch)
    attestation_module.prepare_parity_validation_attestation(
        config=config,
        now=NOW,
    )

    changed = ParityAnalyticalProvenance(
        analytical_contract_version=PROVENANCE.analytical_contract_version,
        source_commit="c" * 40,
        pipeline_config_fingerprint=PROVENANCE.pipeline_config_fingerprint,
    )
    monkeypatch.setattr(
        attestation_module.parity_provenance,
        "current_parity_provenance",
        lambda _config: changed,
    )

    with pytest.raises(
        attestation_module.ParityValidationAttestationError,
        match="source_commit",
    ):
        attestation_module.verify_parity_validation_attestation(config=config)


def test_malformed_attestation_fails_closed(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.parity_validation_attestation_path.write_text(
        json.dumps({"schema_version": 1}),
        encoding="utf-8",
    )

    with pytest.raises(
        attestation_module.ParityValidationAttestationError,
        match="malformed",
    ):
        attestation_module.load_parity_validation_attestation(
            config.parity_validation_attestation_path
        )
