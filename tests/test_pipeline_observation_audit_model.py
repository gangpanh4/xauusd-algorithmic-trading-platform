from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone

import pytest

from core.trading_pipeline.models import (
    PipelineDisposition,
    PipelineObservationAudit,
    PipelineStage,
)


def test_rejected_observation_records_scalar_pipeline_facts() -> None:
    audit = PipelineObservationAudit(
        timestamp=datetime(2026, 1, 2, 3, 4, tzinfo=UTC),
        disposition=PipelineDisposition.REJECTED,
        stage_reached=PipelineStage.TRADE_QUALITY,
        rejection_stage=PipelineStage.TRADE_QUALITY,
        reason_code="TRADE_QUALITY_REJECTED",
        reason="Quality policy rejected the candidate.",
        regime_confirmed=True,
        bos_present=True,
        liquidity_present=True,
        feature_count=12,
        probability_calculated=True,
        probability_accepted=True,
        probability_value=0.72,
        trade_quality_calculated=True,
        trade_quality_approved=False,
        trade_quality_score=0.48,
        confluence_available=True,
        confluence_approved=True,
        confluence_score=0.81,
    )

    assert audit.accepted is False
    assert audit.feature_count == 12
    assert audit.rejection_stage is PipelineStage.TRADE_QUALITY


def test_accepted_observation_requires_final_risk_approval() -> None:
    audit = PipelineObservationAudit(
        timestamp=datetime(2026, 1, 2, tzinfo=UTC),
        disposition=PipelineDisposition.ACCEPTED,
        stage_reached=PipelineStage.APPROVED,
        regime_confirmed=True,
        probability_calculated=True,
        probability_accepted=True,
        trade_quality_calculated=True,
        trade_quality_approved=True,
        confluence_available=True,
        confluence_approved=True,
        signal_generated=True,
        risk_approved=True,
    )

    assert audit.accepted is True

    with pytest.raises(ValueError, match="risk approved"):
        PipelineObservationAudit(
            timestamp=datetime(2026, 1, 2, tzinfo=UTC),
            disposition=PipelineDisposition.ACCEPTED,
            stage_reached=PipelineStage.APPROVED,
            risk_approved=False,
        )


def test_timestamp_is_normalized_to_utc() -> None:
    offset = timezone(timedelta(hours=7))
    audit = PipelineObservationAudit(
        timestamp=datetime(2026, 1, 2, 10, 0, tzinfo=offset),
        disposition=PipelineDisposition.SKIPPED,
        stage_reached=PipelineStage.OBSERVATION,
        reason_code="WARMUP",
        reason="Insufficient completed history.",
    )

    assert audit.timestamp == datetime(2026, 1, 2, 3, 0, tzinfo=UTC)


def test_model_is_immutable() -> None:
    audit = PipelineObservationAudit(
        timestamp=datetime(2026, 1, 2, tzinfo=UTC),
        disposition=PipelineDisposition.SKIPPED,
        stage_reached=PipelineStage.OBSERVATION,
    )

    with pytest.raises(FrozenInstanceError):
        audit.feature_count = 4  # type: ignore[misc]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"timestamp": datetime(2026, 1, 2)}, "timezone-aware"),
        ({"feature_count": -1}, "feature_count"),
        ({"probability_value": float("nan")}, "finite"),
        ({"trade_quality_score": 1.1}, "between 0 and 1"),
        ({"reason_code": ""}, "reason_code"),
    ],
)
def test_invalid_scalar_facts_fail_closed(kwargs: dict[str, object], message: str) -> None:
    base: dict[str, object] = {
        "timestamp": datetime(2026, 1, 2, tzinfo=UTC),
        "disposition": PipelineDisposition.SKIPPED,
        "stage_reached": PipelineStage.OBSERVATION,
    }
    base.update(kwargs)

    with pytest.raises((TypeError, ValueError), match=message):
        PipelineObservationAudit(**base)  # type: ignore[arg-type]


def test_rejected_observation_requires_stage_and_reason_code() -> None:
    with pytest.raises(ValueError, match="rejection_stage"):
        PipelineObservationAudit(
            timestamp=datetime(2026, 1, 2, tzinfo=UTC),
            disposition=PipelineDisposition.REJECTED,
            stage_reached=PipelineStage.PROBABILITY,
            reason_code="PROBABILITY_REJECTED",
        )

    with pytest.raises(ValueError, match="reason_code"):
        PipelineObservationAudit(
            timestamp=datetime(2026, 1, 2, tzinfo=UTC),
            disposition=PipelineDisposition.REJECTED,
            stage_reached=PipelineStage.PROBABILITY,
            rejection_stage=PipelineStage.PROBABILITY,
        )
