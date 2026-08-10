from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from core.data.models import MarketBar
from core.live_trading.parity_evidence import LiveParityEvidence, append_parity_evidence
from core.live_trading.parity_provenance import (
    M5_ANALYTICAL_CONTRACT_V1,
    pipeline_config_fingerprint,
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


def _bar(timestamp: datetime) -> MarketBar:
    return MarketBar(
        timestamp=timestamp,
        open=4000.0,
        high=4005.0,
        low=3998.0,
        close=4003.0,
        tick_volume=1000,
    )


def _evidence(*, schema_version: int = 2) -> LiveParityEvidence:
    timestamp = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    histories = {
        timeframe: (_bar(timestamp - timedelta(minutes=5)), _bar(timestamp))
        for timeframe in Timeframe
    }
    audit = PipelineObservationAudit(
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
        trade_quality_score=0.32,
        confluence_available=True,
        confluence_score=0.10,
    )
    return LiveParityEvidence(
        schema_version=schema_version,
        analytical_contract_version=(
            M5_ANALYTICAL_CONTRACT_V1 if schema_version == 2 else None
        ),
        source_commit=_SOURCE_COMMIT if schema_version == 2 else None,
        pipeline_config_fingerprint=_FINGERPRINT if schema_version == 2 else None,
        captured_at=timestamp + timedelta(minutes=5),
        observation_timestamp=timestamp,
        symbol="XAUUSD",
        bars_by_timeframe=histories,
        account_balance=10_000.0,
        stop_loss_distance=0.01,
        pip_value=0.1,
        tick_size=0.01,
        lot_step=0.01,
        minimum_lot=0.01,
        maximum_lot=100.0,
        expected_audit=audit,
    )


def test_live_parity_evidence_schema_v2_round_trip_exactly() -> None:
    evidence = _evidence()
    payload = evidence.to_payload()

    restored = LiveParityEvidence.from_payload(payload)

    assert restored == evidence
    assert restored.to_payload() == payload
    assert payload["schema_version"] == 2
    assert payload["analytical_contract_version"] == M5_ANALYTICAL_CONTRACT_V1
    assert payload["source_commit"] == _SOURCE_COMMIT
    assert payload["pipeline_config_fingerprint"] == _FINGERPRINT


def test_schema_v1_remains_parseable_without_inferred_provenance() -> None:
    evidence = _evidence(schema_version=1)
    payload = evidence.to_payload()

    restored = LiveParityEvidence.from_payload(payload)

    assert restored == evidence
    assert "analytical_contract_version" not in payload
    assert "source_commit" not in payload
    assert "pipeline_config_fingerprint" not in payload


def test_schema_v2_missing_provenance_fails_closed() -> None:
    payload = _evidence().to_payload()
    del payload["source_commit"]

    with pytest.raises(ValueError, match="invalid live parity evidence payload"):
        LiveParityEvidence.from_payload(payload)


def test_live_parity_evidence_rejects_execution_authority() -> None:
    evidence = _evidence()

    with pytest.raises(ValueError, match="analysis-only"):
        replace(evidence, live_execution_enabled=True, shadow_only=False)


def test_live_parity_evidence_rejects_missing_timeframe() -> None:
    evidence = _evidence()
    histories = dict(evidence.bars_by_timeframe)
    del histories[Timeframe.H4]

    with pytest.raises(ValueError, match="missing H4 parity history"):
        replace(evidence, bars_by_timeframe=histories)


def test_live_parity_evidence_rejects_duplicate_history() -> None:
    evidence = _evidence()
    histories = dict(evidence.bars_by_timeframe)
    latest = histories[Timeframe.M15][-1]
    histories[Timeframe.M15] = (*histories[Timeframe.M15], latest)

    with pytest.raises(ValueError, match="M15 parity history must increase strictly"):
        replace(evidence, bars_by_timeframe=histories)


def test_live_parity_evidence_rejects_out_of_order_history() -> None:
    evidence = _evidence()
    histories = dict(evidence.bars_by_timeframe)
    histories[Timeframe.H1] = tuple(reversed(histories[Timeframe.H1]))

    with pytest.raises(ValueError, match="H1 parity history must increase strictly"):
        replace(evidence, bars_by_timeframe=histories)


def test_live_parity_evidence_rejects_mismatched_audit_timestamp() -> None:
    evidence = _evidence()
    audit = replace(
        evidence.expected_audit,
        timestamp=evidence.observation_timestamp + timedelta(minutes=5),
    )

    with pytest.raises(
        ValueError,
        match="expected audit timestamp must match observation_timestamp",
    ):
        replace(evidence, expected_audit=audit)


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("account_balance", 0.0),
        ("stop_loss_distance", -0.01),
        ("pip_value", float("nan")),
        ("tick_size", float("inf")),
        ("lot_step", 0.0),
    ),
)
def test_live_parity_evidence_rejects_invalid_replay_inputs(
    field_name: str,
    value: float,
) -> None:
    with pytest.raises(ValueError):
        replace(_evidence(), **{field_name: value})


def test_append_parity_evidence_recovers_after_truncated_tail(tmp_path) -> None:
    path = tmp_path / "parity.jsonl"
    path.write_text('{"schema_version": 1', encoding="utf-8")

    evidence = _evidence()
    append_parity_evidence(path, evidence)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == '{"schema_version": 1'
    assert json.loads(lines[1]) == evidence.to_payload()


def test_append_parity_evidence_does_not_add_blank_line(tmp_path) -> None:
    path = tmp_path / "parity.jsonl"
    evidence = _evidence()

    append_parity_evidence(path, evidence)
    append_parity_evidence(path, evidence)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert all(json.loads(line) == evidence.to_payload() for line in lines)
