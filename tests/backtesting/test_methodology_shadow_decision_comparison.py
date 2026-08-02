from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta

from core.backtesting.methodology_observer import MethodologyObservation
from core.backtesting.methodology_outcome_research import (
    MethodologyOutcomeEvaluation,
)
from core.backtesting.methodology_shadow_decision_comparison import (
    MethodologyShadowDecisionComparison,
)
from core.multi_timeframe.enums import MarketBias
from core.strategies.methodology_models import (
    MethodologyCondition,
    MethodologyDirection,
    MethodologyEvaluationStatus,
    MethodologyIdentifier,
    MethodologyResult,
)
from core.strategies.smc_ict_context import PriceLocation, SMCICTContext
from core.trading_pipeline.models import (
    PipelineDisposition,
    PipelineObservationAudit,
    PipelineStage,
)


def _condition(code: str) -> MethodologyCondition:
    return MethodologyCondition(
        code=code,
        description=f"Test condition {code}.",
        required=True,
        evidence_reference=code.lower(),
    )


def _context(timestamp: datetime) -> SMCICTContext:
    return SMCICTContext(
        timestamp=timestamp,
        current_bar_index=1,
        current_price=100.0,
        higher_timeframe_bias=MarketBias.BULLISH,
        h4_structure=None,
        h1_structure=None,
        m15_structure=None,
        m5_structure=None,
        latest_structure_event=None,
        latest_liquidity_sweep=None,
        opposing_liquidity_level=None,
        active_fair_value_gap=None,
        active_order_block=None,
        price_location=PriceLocation.UNKNOWN,
        session_name="London",
        regime_name="TRENDING_BULL",
        missing_capabilities=(),
    )


def _result(
    timestamp: datetime,
    *,
    direction: MethodologyDirection,
    satisfied: tuple[str, ...],
    failed: tuple[str, ...],
    methodology: MethodologyIdentifier = MethodologyIdentifier.SMC,
) -> MethodologyResult:
    status = (
        MethodologyEvaluationStatus.NOT_CONFIRMED
        if failed
        else MethodologyEvaluationStatus.CONFIRMED
    )
    return MethodologyResult(
        methodology=methodology,
        timestamp=timestamp,
        evaluation_status=status,
        direction=direction,
        satisfied_conditions=tuple(_condition(code) for code in satisfied),
        failed_conditions=tuple(_condition(code) for code in failed),
        unavailable_conditions=(),
        reason_codes=("TEST",),
        reason="Shadow comparison test.",
    )


def _observation(
    timestamp: datetime,
    *,
    direction: MethodologyDirection,
    satisfied: tuple[str, ...],
    failed: tuple[str, ...],
) -> MethodologyObservation:
    return MethodologyObservation(
        timestamp=timestamp,
        context=_context(timestamp),
        smc=_result(
            timestamp,
            direction=direction,
            satisfied=satisfied,
            failed=failed,
        ),
        ict=_result(
            timestamp,
            direction=direction,
            satisfied=satisfied,
            failed=failed,
            methodology=MethodologyIdentifier.ICT,
        ),
    )


def _audit(
    timestamp: datetime,
    *,
    accepted: bool,
    reason_code: str = "PROBABILITY_REJECTED",
) -> PipelineObservationAudit:
    if accepted:
        return PipelineObservationAudit(
            timestamp=timestamp,
            disposition=PipelineDisposition.ACCEPTED,
            stage_reached=PipelineStage.APPROVED,
            risk_approved=True,
        )
    return PipelineObservationAudit(
        timestamp=timestamp,
        disposition=PipelineDisposition.REJECTED,
        stage_reached=PipelineStage.PROBABILITY,
        rejection_stage=PipelineStage.PROBABILITY,
        reason_code=reason_code,
        reason="Rejected by active pipeline.",
    )


def _outcome(
    timestamp: datetime,
    *,
    direction: MethodologyDirection,
    favorable: bool,
    return_percent: float,
) -> MethodologyOutcomeEvaluation:
    return MethodologyOutcomeEvaluation(
        observation_timestamp=timestamp,
        methodology=MethodologyIdentifier.SMC,
        evaluation_status=MethodologyEvaluationStatus.NOT_CONFIRMED,
        direction=direction,
        horizon_bars=24,
        horizon_complete=True,
        source_price=100.0,
        terminal_timestamp=timestamp + timedelta(minutes=120),
        terminal_price=100.0 + return_percent,
        directional_move=return_percent,
        directional_return_pct=return_percent,
        maximum_favorable_excursion=max(return_percent, 0.0) + 1.0,
        maximum_adverse_excursion=1.0,
        favorable_terminal_outcome=favorable,
        session_name="London",
        regime_name="TRENDING_BULL",
    )


def test_compares_shadow_eligibility_with_active_decision() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = (
        _observation(
            start,
            direction=MethodologyDirection.BULLISH,
            satisfied=("ORDER_BLOCK_PRESENT", "STRUCTURE_EVENT_ALIGNED"),
            failed=(),
        ),
        _observation(
            start + timedelta(minutes=5),
            direction=MethodologyDirection.BULLISH,
            satisfied=("ORDER_BLOCK_PRESENT",),
            failed=("STRUCTURE_EVENT_ALIGNED",),
        ),
    )
    audits = (
        _audit(start, accepted=False),
        _audit(start + timedelta(minutes=5), accepted=True),
    )
    outcomes = (
        _outcome(
            start,
            direction=MethodologyDirection.BULLISH,
            favorable=True,
            return_percent=1.0,
        ),
        _outcome(
            start + timedelta(minutes=5),
            direction=MethodologyDirection.BULLISH,
            favorable=False,
            return_percent=-1.0,
        ),
    )

    payload, rows = MethodologyShadowDecisionComparison().calculate(
        observations,
        audits,
        outcomes,
    )

    bullish_rows = [
        row
        for row in rows
        if row["Variant"]
        == "VARIANT_A_BULLISH_ORDER_BLOCK_STRUCTURE"
    ]
    assert bullish_rows[0]["Alignment Method"] == "EXACT"
    assert bullish_rows[0]["Alignment Lag Minutes"] == 0.0
    assert bullish_rows[0]["Agreement"] == "SHADOW_ONLY"
    assert bullish_rows[0]["Research Classification"] == (
        "SHADOW_TRUE_POSITIVE"
    )
    assert bullish_rows[1]["Agreement"] == "ACTIVE_ONLY"
    assert bullish_rows[1]["Research Classification"] == (
        "SHADOW_TRUE_NEGATIVE"
    )
    summary = payload["variants"][0]
    assert summary["shadow_eligible_count"] == 1
    assert summary["active_accepted_count"] == 1
    assert summary["shadow_only_rejection_reason_counts"] == {
        "PROBABILITY_REJECTED": 1
    }
    assert payload["active_decision_modified"] is False


def test_counts_shadow_false_positive_and_false_negative() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = (
        _observation(
            start,
            direction=MethodologyDirection.BEARISH,
            satisfied=("ORDER_BLOCK_PRESENT",),
            failed=("LIQUIDITY_SWEEP_COMPATIBLE",),
        ),
        _observation(
            start + timedelta(minutes=5),
            direction=MethodologyDirection.BEARISH,
            satisfied=("LIQUIDITY_SWEEP_COMPATIBLE",),
            failed=("ORDER_BLOCK_PRESENT",),
        ),
    )
    audits = (
        _audit(start, accepted=False),
        _audit(start + timedelta(minutes=5), accepted=False),
    )
    outcomes = (
        _outcome(
            start,
            direction=MethodologyDirection.BEARISH,
            favorable=False,
            return_percent=-1.0,
        ),
        _outcome(
            start + timedelta(minutes=5),
            direction=MethodologyDirection.BEARISH,
            favorable=True,
            return_percent=1.0,
        ),
    )

    payload, _ = MethodologyShadowDecisionComparison().calculate(
        observations,
        audits,
        outcomes,
    )

    summary = next(
        item
        for item in payload["variants"]
        if item["direction"] == "BEARISH"
    )
    assert summary["shadow_false_positive_count"] == 1
    assert summary["shadow_false_negative_count"] == 1


def test_export_writes_csv_json_and_window_metadata(tmp_path) -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    observation = _observation(
        timestamp,
        direction=MethodologyDirection.BULLISH,
        satisfied=("ORDER_BLOCK_PRESENT", "STRUCTURE_EVENT_ALIGNED"),
        failed=(),
    )

    csv_path, json_path = MethodologyShadowDecisionComparison(
        tmp_path
    ).export(
        (observation,),
        (_audit(timestamp, accepted=False),),
        (
            _outcome(
                timestamp,
                direction=MethodologyDirection.BULLISH,
                favorable=True,
                return_percent=1.0,
            ),
        ),
        window_metadata={
            "requested_end_time": "2026-04-09T23:59:00+00:00"
        },
    )

    with csv_path.open(newline="", encoding="utf-8") as file:
        assert list(csv.DictReader(file))
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["window_metadata"]["requested_end_time"] == (
        "2026-04-09T23:59:00+00:00"
    )
    assert payload["trade_authority"] is False


def test_aligns_active_audit_asof_backward_without_lookahead() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    methodology_timestamp = start + timedelta(minutes=10)
    audit_timestamp = start + timedelta(minutes=15)
    future_timestamp = start + timedelta(minutes=20)

    observations = (
        _observation(
            methodology_timestamp,
            direction=MethodologyDirection.BULLISH,
            satisfied=(
                "ORDER_BLOCK_PRESENT",
                "STRUCTURE_EVENT_ALIGNED",
            ),
            failed=(),
        ),
        _observation(
            future_timestamp,
            direction=MethodologyDirection.BEARISH,
            satisfied=("ORDER_BLOCK_PRESENT",),
            failed=("LIQUIDITY_SWEEP_COMPATIBLE",),
        ),
    )
    outcomes = (
        _outcome(
            methodology_timestamp,
            direction=MethodologyDirection.BULLISH,
            favorable=True,
            return_percent=1.0,
        ),
        _outcome(
            future_timestamp,
            direction=MethodologyDirection.BEARISH,
            favorable=False,
            return_percent=-1.0,
        ),
    )

    payload, rows = MethodologyShadowDecisionComparison().calculate(
        observations,
        (_audit(audit_timestamp, accepted=False),),
        outcomes,
    )

    bullish_row = next(
        row
        for row in rows
        if row["Direction"] == "BULLISH"
    )
    assert bullish_row["Active Audit Timestamp"] == (
        audit_timestamp.isoformat()
    )
    assert bullish_row["Methodology Timestamp"] == (
        methodology_timestamp.isoformat()
    )
    assert bullish_row["Alignment Method"] == "ASOF_BACKWARD"
    assert bullish_row["Alignment Lag Minutes"] == 5.0
    assert payload["aligned_audit_count"] == 1
    assert payload["exact_alignment_count"] == 0
    assert payload["asof_backward_alignment_count"] == 1
    assert payload["unmatched_audit_count"] == 0
    assert payload["alignment_policy"][
        "future_methodology_observations_allowed"
    ] is False


def test_rejects_alignment_when_backward_lag_exceeds_limit() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    audit_timestamp = start + timedelta(minutes=20)
    later_timestamp = start + timedelta(minutes=30)
    observations = (
        _observation(
            start,
            direction=MethodologyDirection.BULLISH,
            satisfied=(
                "ORDER_BLOCK_PRESENT",
                "STRUCTURE_EVENT_ALIGNED",
            ),
            failed=(),
        ),
        _observation(
            later_timestamp,
            direction=MethodologyDirection.BULLISH,
            satisfied=(
                "ORDER_BLOCK_PRESENT",
                "STRUCTURE_EVENT_ALIGNED",
            ),
            failed=(),
        ),
    )
    outcomes = (
        _outcome(
            start,
            direction=MethodologyDirection.BULLISH,
            favorable=True,
            return_percent=1.0,
        ),
        _outcome(
            later_timestamp,
            direction=MethodologyDirection.BULLISH,
            favorable=True,
            return_percent=1.0,
        ),
    )

    payload, rows = MethodologyShadowDecisionComparison(
        maximum_alignment_lag_minutes=15,
    ).calculate(
        observations,
        (_audit(audit_timestamp, accepted=False),),
        outcomes,
    )

    assert rows == []
    assert payload["aligned_audit_count"] == 0
    assert payload["unmatched_audit_count"] == 1
    assert payload["unmatched_audits"] == [
        {
            "active_audit_timestamp": audit_timestamp.isoformat(),
            "candidate_methodology_timestamp": start.isoformat(),
            "candidate_lag_minutes": 20.0,
            "maximum_alignment_lag_minutes": 15,
            "reason": "ALIGNMENT_LAG_EXCEEDED",
        }
    ]
    assert payload["common_window"][
        "alignment_coverage_rate_inside_window"
    ] == 0.0


def test_classifies_audits_outside_common_window() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    methodology_start = start + timedelta(minutes=5)
    common_end = start + timedelta(minutes=20)
    audits = (
        _audit(start, accepted=False),
        _audit(methodology_start, accepted=False),
        _audit(common_end, accepted=False),
        _audit(common_end + timedelta(minutes=5), accepted=False),
    )
    observations = (
        _observation(
            methodology_start,
            direction=MethodologyDirection.BULLISH,
            satisfied=(
                "ORDER_BLOCK_PRESENT",
                "STRUCTURE_EVENT_ALIGNED",
            ),
            failed=(),
        ),
        _observation(
            common_end,
            direction=MethodologyDirection.BULLISH,
            satisfied=(
                "ORDER_BLOCK_PRESENT",
                "STRUCTURE_EVENT_ALIGNED",
            ),
            failed=(),
        ),
        _observation(
            common_end + timedelta(minutes=5),
            direction=MethodologyDirection.BULLISH,
            satisfied=(
                "ORDER_BLOCK_PRESENT",
                "STRUCTURE_EVENT_ALIGNED",
            ),
            failed=(),
        ),
    )
    outcomes = (
        _outcome(
            methodology_start,
            direction=MethodologyDirection.BULLISH,
            favorable=True,
            return_percent=1.0,
        ),
        _outcome(
            common_end,
            direction=MethodologyDirection.BULLISH,
            favorable=True,
            return_percent=1.0,
        ),
    )

    payload, rows = MethodologyShadowDecisionComparison().calculate(
        observations,
        audits,
        outcomes,
    )

    assert len(rows) == 2
    assert payload["common_window"] == {
        "basis": (
            "INTERSECTION_OF_ACTIVE_AUDITS_"
            "METHODOLOGY_OBSERVATIONS_"
            "AND_COMPLETE_24_BAR_OUTCOMES"
        ),
        "start": methodology_start.isoformat(),
        "end": common_end.isoformat(),
        "audit_count_before_window": 1,
        "audit_count_inside_window": 2,
        "audit_count_after_window": 1,
        "methodology_observation_count_inside_window": 2,
        "complete_outcome_timestamp_count_inside_window": 2,
        "alignment_coverage_rate_inside_window": 1.0,
        "outside_window_classification": "OUTSIDE_COMMON_WINDOW",
    }
    assert payload["unmatched_audit_count"] == 0
    assert payload["outside_common_window"] == {
        "before_count": 1,
        "before_first_timestamp": start.isoformat(),
        "before_last_timestamp": start.isoformat(),
        "after_count": 1,
        "after_first_timestamp": (
            common_end + timedelta(minutes=5)
        ).isoformat(),
        "after_last_timestamp": (
            common_end + timedelta(minutes=5)
        ).isoformat(),
        "classification": "OUTSIDE_COMMON_WINDOW",
    }


def test_reports_empty_common_window_when_required_domain_missing() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observation = _observation(
        start,
        direction=MethodologyDirection.BULLISH,
        satisfied=("ORDER_BLOCK_PRESENT", "STRUCTURE_EVENT_ALIGNED"),
        failed=(),
    )

    payload, rows = MethodologyShadowDecisionComparison().calculate(
        (observation,),
        (_audit(start, accepted=False),),
        (),
    )

    assert rows == []
    assert payload["common_window"]["start"] is None
    assert payload["common_window"]["end"] is None
    assert payload["common_window"][
        "audit_count_inside_window"
    ] == 0
    assert payload["aligned_audit_count"] == 0


def test_alignment_limit_validation() -> None:
    import pytest

    with pytest.raises(TypeError):
        MethodologyShadowDecisionComparison(
            maximum_alignment_lag_minutes=True,
        )
    with pytest.raises(ValueError):
        MethodologyShadowDecisionComparison(
            maximum_alignment_lag_minutes=-1,
        )
