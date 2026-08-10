from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import core.live_trading.engine as engine_module
import core.live_trading.parity_provenance as provenance_module
from core.data.models import MarketBar
from core.live_trading.config import LiveTradingConfig
from core.live_trading.engine import LiveTradingEngine
from core.live_trading.parity_provenance import (
    M5_ANALYTICAL_CONTRACT_V1,
    ParityAnalyticalProvenance,
    ParityProvenanceError,
    pipeline_config_fingerprint,
    resolve_source_commit,
)
from core.multi_timeframe.enums import Timeframe
from core.trading_pipeline.config import TradingPipelineConfig
from core.trading_pipeline.models import (
    PipelineDisposition,
    PipelineObservationAudit,
    PipelineStage,
)

_SOURCE_COMMIT = "a" * 40
_FINGERPRINT = pipeline_config_fingerprint(TradingPipelineConfig())


def test_pipeline_config_fingerprint_is_deterministic() -> None:
    first = pipeline_config_fingerprint(TradingPipelineConfig())
    second = pipeline_config_fingerprint(TradingPipelineConfig())

    assert first == second
    assert len(first) == 64


def test_material_pipeline_configuration_changes_fingerprint() -> None:
    baseline = TradingPipelineConfig()
    changed_regime = replace(
        baseline.regime_detector,
        trend_confirmation_bars=baseline.regime_detector.trend_confirmation_bars + 1,
    )
    changed = replace(baseline, regime_detector=changed_regime)

    assert pipeline_config_fingerprint(changed) != pipeline_config_fingerprint(baseline)


def test_live_execution_controls_do_not_change_analytical_fingerprint() -> None:
    safe = LiveTradingConfig(
        live_execution_enabled=False,
        demo_execution_approved=False,
        execution_kill_switch_enabled=True,
    )
    canary_controls = LiveTradingConfig(
        live_execution_enabled=True,
        demo_execution_approved=True,
        execution_kill_switch_enabled=False,
    )

    assert pipeline_config_fingerprint(safe.pipeline) == pipeline_config_fingerprint(
        canary_controls.pipeline
    )


def test_debug_logging_is_not_part_of_analytical_fingerprint() -> None:
    baseline = TradingPipelineConfig()
    changed = replace(baseline, debug_logging=True)

    assert pipeline_config_fingerprint(changed) == pipeline_config_fingerprint(baseline)


def test_source_commit_resolution_requires_clean_tree_when_requested(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_run(root: Path, *arguments: str) -> str:
        if arguments == ("rev-parse", "--show-toplevel"):
            return str(tmp_path)
        if arguments == ("rev-parse", "--verify", "HEAD"):
            return _SOURCE_COMMIT
        if arguments == ("status", "--porcelain=v1", "--untracked-files=normal"):
            return " M core/trading_pipeline/pipeline.py"
        raise AssertionError(arguments)

    monkeypatch.setattr(provenance_module, "_run_git", fake_run)

    with pytest.raises(ParityProvenanceError, match="clean Git working tree"):
        resolve_source_commit(require_clean=True, repository_root=tmp_path)


def test_source_commit_resolution_accepts_clean_exact_checkout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_run(root: Path, *arguments: str) -> str:
        if arguments == ("rev-parse", "--show-toplevel"):
            return str(tmp_path)
        if arguments == ("rev-parse", "--verify", "HEAD"):
            return _SOURCE_COMMIT
        if arguments == ("status", "--porcelain=v1", "--untracked-files=normal"):
            return ""
        raise AssertionError(arguments)

    monkeypatch.setattr(provenance_module, "_run_git", fake_run)

    assert (
        resolve_source_commit(require_clean=True, repository_root=tmp_path)
        == _SOURCE_COMMIT
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


def _audit(timestamp: datetime) -> PipelineObservationAudit:
    return PipelineObservationAudit(
        timestamp=timestamp,
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


def test_engine_records_schema_v2_authoritative_provenance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    timestamp = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    config = LiveTradingConfig(
        parity_recording_enabled=True,
        parity_evidence_path=tmp_path / "parity.jsonl",
    )
    engine = LiveTradingEngine(config)
    engine.pipeline._last_observation_audit = _audit(timestamp)
    provenance = ParityAnalyticalProvenance(
        analytical_contract_version=M5_ANALYTICAL_CONTRACT_V1,
        source_commit=_SOURCE_COMMIT,
        pipeline_config_fingerprint=_FINGERPRINT,
    )
    monkeypatch.setattr(
        engine_module,
        "current_parity_provenance",
        lambda pipeline_config: provenance,
    )
    recorded = []
    monkeypatch.setattr(
        engine_module,
        "append_parity_evidence",
        lambda path, evidence: recorded.append((path, evidence)),
    )
    histories = {
        timeframe: (
            _bar(timestamp - timedelta(minutes=5)),
            _bar(timestamp),
        )
        for timeframe in Timeframe
    }

    engine._record_parity_evidence(
        timestamp=timestamp,
        parity_context=(
            histories,
            10_000.0,
            0.01,
            0.1,
            0.01,
            0.01,
            0.01,
            100.0,
        ),
    )

    assert len(recorded) == 1
    path, evidence = recorded[0]
    assert path == config.parity_evidence_path
    assert evidence.schema_version == 2
    assert evidence.analytical_contract_version == M5_ANALYTICAL_CONTRACT_V1
    assert evidence.source_commit == _SOURCE_COMMIT
    assert evidence.pipeline_config_fingerprint == _FINGERPRINT
    assert evidence.live_execution_enabled is False
    assert evidence.shadow_only is True
    assert evidence.trade_executed is False
