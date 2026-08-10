from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest

import core.live_trading.parity_evidence_prepare as prepare_module
import core.live_trading.parity_provenance as provenance_module
from core.data.models import MarketBar
from core.live_trading.config import LiveTradingConfig
from core.live_trading.execution_concurrency import (
    LocalExecutionLock,
    build_execution_lock_path,
)
from core.live_trading.parity_evidence import LiveParityEvidence
from core.live_trading.parity_evidence_prepare import (
    ParityEvidenceLifecycleError,
    retire_incompatible_parity_evidence,
)
from core.live_trading.parity_provenance import (
    CURRENT_PARITY_HISTORY_CONTRACT_VERSION,
    M5_ANALYTICAL_CONTRACT_V1,
    PARITY_EVIDENCE_SCHEMA_VERSION,
    pipeline_config_fingerprint,
)
from core.multi_timeframe.enums import Timeframe
from core.trading_pipeline.config import TradingPipelineConfig
from core.trading_pipeline.models import (
    PipelineDisposition,
    PipelineObservationAudit,
    PipelineStage,
)

_TIMESTAMP = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
_SOURCE_COMMIT = "a" * 40
_FINGERPRINT = pipeline_config_fingerprint(TradingPipelineConfig())


def _config(tmp_path: Path) -> LiveTradingConfig:
    return LiveTradingConfig(
        parity_evidence_path=tmp_path / "runtime" / "live_parity_evidence.jsonl",
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


def _audit() -> PipelineObservationAudit:
    return PipelineObservationAudit(
        timestamp=_TIMESTAMP,
        disposition=PipelineDisposition.REJECTED,
        stage_reached=PipelineStage.RISK,
        rejection_stage=PipelineStage.PROBABILITY,
        reason_code="PROBABILITY_REJECTED",
        reason="Probability policy rejected the observation.",
        regime_confirmed=True,
        feature_count=31,
        probability_calculated=True,
        probability_accepted=False,
        probability_value=0.57,
        trade_quality_calculated=True,
        trade_quality_approved=False,
        trade_quality_score=0.32,
        confluence_available=True,
        confluence_approved=False,
        confluence_score=0.1,
        signal_generated=False,
        risk_approved=False,
    )


def _evidence(*, schema_version: int) -> LiveParityEvidence:
    source_timeframes = (
        Timeframe.M5,
        Timeframe.M15,
        Timeframe.H1,
        Timeframe.H4,
    )
    required_timeframes = (
        source_timeframes
        if schema_version == PARITY_EVIDENCE_SCHEMA_VERSION
        else tuple(Timeframe)
    )
    histories = {
        timeframe: (
            _bar(_TIMESTAMP - timedelta(minutes=5)),
            _bar(_TIMESTAMP),
        )
        for timeframe in required_timeframes
    }
    versioned = schema_version in {2, PARITY_EVIDENCE_SCHEMA_VERSION}
    return LiveParityEvidence(
        schema_version=schema_version,
        analytical_contract_version=(
            M5_ANALYTICAL_CONTRACT_V1 if versioned else None
        ),
        source_commit=_SOURCE_COMMIT if versioned else None,
        pipeline_config_fingerprint=_FINGERPRINT if versioned else None,
        history_contract_version=(
            CURRENT_PARITY_HISTORY_CONTRACT_VERSION
            if schema_version == PARITY_EVIDENCE_SCHEMA_VERSION
            else None
        ),
        captured_at=_TIMESTAMP + timedelta(minutes=5),
        observation_timestamp=_TIMESTAMP,
        symbol="XAUUSD",
        bars_by_timeframe=histories,
        account_balance=10_000.0,
        stop_loss_distance=0.01,
        pip_value=0.1,
        tick_size=0.01,
        lot_step=0.01,
        minimum_lot=0.01,
        maximum_lot=100.0,
        expected_audit=_audit(),
    )


def _row_bytes(evidence: LiveParityEvidence) -> bytes:
    return (
        json.dumps(evidence.to_payload(), separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    active = tmp_path / "runtime" / "live_parity_evidence.jsonl"
    archive = tmp_path / "runtime" / "archive" / "live_parity_evidence"
    active.parent.mkdir(parents=True, exist_ok=True)
    return active, archive


def test_legacy_artifact_archives_exact_bytes_and_installs_empty_active(
    tmp_path: Path,
) -> None:
    active, archive = _paths(tmp_path)
    exact = _row_bytes(_evidence(schema_version=1))
    active.write_bytes(exact)

    result = retire_incompatible_parity_evidence(
        config=_config(tmp_path),
        active_path=active,
        archive_root=archive,
    )

    digest = sha256(exact).hexdigest()
    expected_archive = archive / f"{digest}.jsonl"
    assert result.retired is True
    assert result.evidence_count == 1
    assert result.legacy_unversioned_count == 1
    assert result.provenance_mismatch_count == 0
    assert result.artifact_sha256 == digest
    assert result.archive_path == expected_archive
    assert expected_archive.read_bytes() == exact
    assert active.read_bytes() == b""


def test_archive_filename_is_deterministic_content_address(tmp_path: Path) -> None:
    active, archive = _paths(tmp_path)
    exact = _row_bytes(_evidence(schema_version=1))
    active.write_bytes(exact)

    result = retire_incompatible_parity_evidence(
        config=_config(tmp_path),
        active_path=active,
        archive_root=archive,
    )

    assert result.archive_path == archive / f"{sha256(exact).hexdigest()}.jsonl"


def test_identical_existing_archive_is_idempotently_satisfied(tmp_path: Path) -> None:
    active, archive = _paths(tmp_path)
    exact = _row_bytes(_evidence(schema_version=1))
    digest = sha256(exact).hexdigest()
    archive.mkdir(parents=True)
    (archive / f"{digest}.jsonl").write_bytes(exact)
    active.write_bytes(exact)

    result = retire_incompatible_parity_evidence(
        config=_config(tmp_path),
        active_path=active,
        archive_root=archive,
    )

    assert result.retired is True
    assert result.archive_path is not None
    assert result.archive_path.read_bytes() == exact
    assert active.read_bytes() == b""


def test_conflicting_archive_fails_closed_and_preserves_active(tmp_path: Path) -> None:
    active, archive = _paths(tmp_path)
    exact = _row_bytes(_evidence(schema_version=1))
    digest = sha256(exact).hexdigest()
    archive.mkdir(parents=True)
    collision = archive / f"{digest}.jsonl"
    collision.write_bytes(b"different")
    active.write_bytes(exact)

    with pytest.raises(ParityEvidenceLifecycleError, match="different bytes"):
        retire_incompatible_parity_evidence(
            config=_config(tmp_path),
            active_path=active,
            archive_root=archive,
        )

    assert active.read_bytes() == exact
    assert collision.read_bytes() == b"different"


def test_archive_fsync_failure_preserves_active(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    active, archive = _paths(tmp_path)
    exact = _row_bytes(_evidence(schema_version=1))
    active.write_bytes(exact)
    real_fsync = prepare_module._fsync_directory

    def fail_archive(directory: Path) -> None:
        if directory == archive:
            raise OSError("injected archive fsync failure")
        real_fsync(directory)

    monkeypatch.setattr(prepare_module, "_fsync_directory", fail_archive)

    with pytest.raises(ParityEvidenceLifecycleError, match="durably archive"):
        retire_incompatible_parity_evidence(
            config=_config(tmp_path),
            active_path=active,
            archive_root=archive,
        )

    assert active.read_bytes() == exact


def test_active_directory_fsync_failure_rolls_back_original(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    active, archive = _paths(tmp_path)
    exact = _row_bytes(_evidence(schema_version=1))
    active.write_bytes(exact)
    real_fsync = prepare_module._fsync_directory
    active_parent_calls = 0

    def fail_post_replace(directory: Path) -> None:
        nonlocal active_parent_calls
        if directory == active.parent:
            active_parent_calls += 1
            if active_parent_calls == 2:
                raise OSError("injected active directory fsync failure")
        real_fsync(directory)

    monkeypatch.setattr(prepare_module, "_fsync_directory", fail_post_replace)

    with pytest.raises(ParityEvidenceLifecycleError, match="original artifact was restored"):
        retire_incompatible_parity_evidence(
            config=_config(tmp_path),
            active_path=active,
            archive_root=archive,
        )

    assert active.read_bytes() == exact


def test_previous_schema_v2_is_archived_as_incompatible(
    tmp_path: Path,
) -> None:
    active, archive = _paths(tmp_path)
    exact = _row_bytes(_evidence(schema_version=2))
    active.write_bytes(exact)

    result = retire_incompatible_parity_evidence(
        config=_config(tmp_path),
        active_path=active,
        archive_root=archive,
    )

    assert result.retired is True
    assert result.evidence_count == 1
    assert result.legacy_unversioned_count == 0
    assert result.provenance_mismatch_count == 1
    assert result.archive_path is not None
    assert result.archive_path.read_bytes() == exact
    assert active.read_bytes() == b""


def test_current_compatible_schema_v3_is_not_retired(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    active, archive = _paths(tmp_path)
    exact = _row_bytes(_evidence(schema_version=PARITY_EVIDENCE_SCHEMA_VERSION))
    active.write_bytes(exact)
    monkeypatch.setattr(
        provenance_module,
        "resolve_source_commit",
        lambda **kwargs: _SOURCE_COMMIT,
    )

    with pytest.raises(ParityEvidenceLifecycleError, match="must not be retired"):
        retire_incompatible_parity_evidence(
            config=_config(tmp_path),
            active_path=active,
            archive_root=archive,
        )

    assert active.read_bytes() == exact
    if archive.exists():
        assert list(archive.glob("*.jsonl")) == []


def test_malformed_active_evidence_fails_closed(tmp_path: Path) -> None:
    active, archive = _paths(tmp_path)
    active.write_bytes(b"{not-json}\n")

    with pytest.raises(ParityEvidenceLifecycleError, match="malformed JSON"):
        retire_incompatible_parity_evidence(
            config=_config(tmp_path),
            active_path=active,
            archive_root=archive,
        )

    assert active.read_bytes() == b"{not-json}\n"


def test_lifecycle_lock_conflict_fails_closed(tmp_path: Path) -> None:
    active, archive = _paths(tmp_path)
    exact = _row_bytes(_evidence(schema_version=1))
    active.write_bytes(exact)
    lock = LocalExecutionLock(
        build_execution_lock_path(active, scope="parity-evidence-lifecycle"),
        purpose="parity evidence lifecycle",
    )
    owner = lock.acquire()
    try:
        with pytest.raises(ParityEvidenceLifecycleError, match="ownership is uncertain"):
            retire_incompatible_parity_evidence(
                config=_config(tmp_path),
                active_path=active,
                archive_root=archive,
            )
        assert active.read_bytes() == exact
    finally:
        lock.release(owner)


def test_prepare_module_has_no_mt5_or_broker_mutation_surface() -> None:
    source = inspect.getsource(prepare_module)

    assert "MetaTrader5" not in source
    assert "core.mt5_execution" not in source
    assert "order_check" not in source
    assert "order_send" not in source
    assert "_authorize_broker_mutation" not in source
    assert "demo_execution_authorization" not in source
    assert "--force" not in source
    assert "--ignore-provenance" not in source
    assert "--delete" not in source
    assert "--skip-archive" not in source
