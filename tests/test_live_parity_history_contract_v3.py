from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from core.data.models import MarketBar
from core.live_trading.parity_evidence import (
    PARITY_SOURCE_TIMEFRAMES,
    LiveParityEvidence,
)
from core.live_trading.parity_provenance import (
    CURRENT_PARITY_HISTORY_CONTRACT_VERSION,
    M5_ANALYTICAL_CONTRACT_V1,
    PARITY_EVIDENCE_SCHEMA_VERSION,
    ParityAnalyticalProvenance,
    ParityResultClassification,
    assess_payload_provenance,
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
_TIMESTAMP = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)


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


def _v3() -> LiveParityEvidence:
    histories = {
        timeframe: (
            _bar(_TIMESTAMP - timedelta(minutes=5)),
            _bar(_TIMESTAMP),
        )
        for timeframe in PARITY_SOURCE_TIMEFRAMES
    }
    return LiveParityEvidence(
        schema_version=PARITY_EVIDENCE_SCHEMA_VERSION,
        analytical_contract_version=M5_ANALYTICAL_CONTRACT_V1,
        source_commit=_SOURCE_COMMIT,
        pipeline_config_fingerprint=_FINGERPRINT,
        history_contract_version=CURRENT_PARITY_HISTORY_CONTRACT_VERSION,
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


def test_v3_round_trip_persists_only_authoritative_source_histories() -> None:
    evidence = _v3()
    payload = evidence.to_payload()

    assert payload["schema_version"] == PARITY_EVIDENCE_SCHEMA_VERSION
    assert payload["history_contract_version"] == (
        CURRENT_PARITY_HISTORY_CONTRACT_VERSION
    )
    assert set(payload["bars_by_timeframe"]) == {"M5", "M15", "H1", "H4"}

    restored = LiveParityEvidence.from_payload(payload)

    assert restored == evidence
    assert tuple(restored.bars_by_timeframe) == PARITY_SOURCE_TIMEFRAMES


@pytest.mark.parametrize("timeframe", PARITY_SOURCE_TIMEFRAMES)
def test_v3_requires_every_authoritative_source_timeframe(
    timeframe: Timeframe,
) -> None:
    evidence = _v3()
    histories = dict(evidence.bars_by_timeframe)
    del histories[timeframe]

    with pytest.raises(
        ValueError,
        match=rf"missing {timeframe.value} parity history",
    ):
        replace(evidence, bars_by_timeframe=histories)


@pytest.mark.parametrize("timeframe", (Timeframe.DAILY, Timeframe.WEEKLY))
def test_v3_rejects_persisted_derived_timeframe_authority(
    timeframe: Timeframe,
) -> None:
    evidence = _v3()
    histories = dict(evidence.bars_by_timeframe)
    histories[timeframe] = (
        _bar(_TIMESTAMP - timedelta(minutes=5)),
        _bar(_TIMESTAMP),
    )

    with pytest.raises(ValueError, match="derived"):
        replace(evidence, bars_by_timeframe=histories)


def test_v3_payload_requires_explicit_history_contract() -> None:
    payload = _v3().to_payload()
    del payload["history_contract_version"]

    with pytest.raises(ValueError, match="invalid live parity evidence payload"):
        LiveParityEvidence.from_payload(payload)


def test_history_contract_mismatch_is_provenance_mismatch() -> None:
    payload = _v3().to_payload()
    payload["history_contract_version"] = "OTHER_HISTORY_CONTRACT_V1"
    current = ParityAnalyticalProvenance(
        analytical_contract_version=M5_ANALYTICAL_CONTRACT_V1,
        source_commit=_SOURCE_COMMIT,
        pipeline_config_fingerprint=_FINGERPRINT,
    )

    assessment = assess_payload_provenance(payload, current)

    assert assessment.compatible is False
    assert assessment.classification == ParityResultClassification.PROVENANCE_MISMATCH
    assert assessment.diagnostics[0]["field"] == "history_contract_version"
