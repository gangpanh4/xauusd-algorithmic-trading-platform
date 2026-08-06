from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.data.models import MarketBar
from core.live_trading.parity_evidence import LiveParityEvidence
from core.multi_timeframe.enums import Timeframe
from core.trading_pipeline.models import (
    PipelineDisposition,
    PipelineObservationAudit,
    PipelineStage,
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


def _evidence() -> LiveParityEvidence:
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


def test_live_parity_evidence_round_trip() -> None:
    evidence = _evidence()

    restored = LiveParityEvidence.from_payload(evidence.to_payload())

    assert restored.observation_timestamp == evidence.observation_timestamp
    assert restored.expected_audit == evidence.expected_audit
    assert restored.bars_by_timeframe[Timeframe.M5] == evidence.bars_by_timeframe[Timeframe.M5]
    assert restored.live_execution_enabled is False
    assert restored.shadow_only is True
    assert restored.trade_executed is False


def test_live_parity_evidence_rejects_execution_authority() -> None:
    evidence = _evidence()

    with pytest.raises(ValueError, match="analysis-only"):
        LiveParityEvidence(
            captured_at=evidence.captured_at,
            observation_timestamp=evidence.observation_timestamp,
            symbol=evidence.symbol,
            bars_by_timeframe=evidence.bars_by_timeframe,
            account_balance=evidence.account_balance,
            stop_loss_distance=evidence.stop_loss_distance,
            pip_value=evidence.pip_value,
            tick_size=evidence.tick_size,
            lot_step=evidence.lot_step,
            minimum_lot=evidence.minimum_lot,
            maximum_lot=evidence.maximum_lot,
            expected_audit=evidence.expected_audit,
            live_execution_enabled=True,
            shadow_only=False,
        )
