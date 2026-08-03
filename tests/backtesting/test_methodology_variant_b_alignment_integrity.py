from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from core.backtesting.methodology_observer import MethodologyObservation
from core.backtesting.methodology_variant_b_alignment_integrity import (
    MethodologyVariantBAlignmentIntegrity,
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


@dataclass(frozen=True)
class _Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float


def _condition(code: str) -> MethodologyCondition:
    return MethodologyCondition(
        code=code,
        description=code,
        required=True,
        evidence_reference=code.lower(),
    )


def _result(
    timestamp: datetime,
    methodology: MethodologyIdentifier,
) -> MethodologyResult:
    return MethodologyResult(
        methodology=methodology,
        timestamp=timestamp,
        evaluation_status=MethodologyEvaluationStatus.NOT_CONFIRMED,
        direction=MethodologyDirection.BEARISH,
        satisfied_conditions=(),
        failed_conditions=(
            _condition("LIQUIDITY_SWEEP_COMPATIBLE"),
        ),
        unavailable_conditions=(),
        reason_codes=("TEST",),
        reason="test",
    )


def _observation(timestamp: datetime) -> MethodologyObservation:
    context = SMCICTContext(
        timestamp=timestamp,
        current_bar_index=1,
        current_price=100.0,
        higher_timeframe_bias=MarketBias.BEARISH,
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
        regime_name="RANGING",
        missing_capabilities=(),
    )
    return MethodologyObservation(
        timestamp=timestamp,
        context=context,
        smc=_result(timestamp, MethodologyIdentifier.SMC),
        ict=_result(timestamp, MethodologyIdentifier.ICT),
    )


def _bars(start: datetime, count: int = 160) -> tuple[_Bar, ...]:
    """Create bars that close each shadow position on its entry candle.

    ATR before the first candidate is 2.0. From bar 21 onward, the high
    reaches 103.0, which is sufficient to hit the bearish ATR stop and
    release the one-position lock before a following candidate.
    """

    values: list[_Bar] = []
    for index in range(count):
        high = 103.0 if index >= 21 else 101.0
        values.append(
            _Bar(
                timestamp=start + timedelta(minutes=5 * index),
                open=100.0,
                high=high,
                low=99.0,
                close=100.0,
            )
        )
    return tuple(values)


def _audit(timestamp: datetime) -> PipelineObservationAudit:
    return PipelineObservationAudit(
        timestamp=timestamp,
        disposition=PipelineDisposition.REJECTED,
        stage_reached=PipelineStage.PROBABILITY,
        rejection_stage=PipelineStage.PROBABILITY,
        reason_code="PROBABILITY_REJECTED",
        reason="test",
        probability_calculated=True,
        probability_accepted=False,
        probability_value=0.4,
    )


def test_separates_exact_and_forward_datasets() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = (
        _observation(start + timedelta(minutes=100)),
        _observation(start + timedelta(minutes=130)),
    )
    audits = (
        _audit(start + timedelta(minutes=100)),
        _audit(start + timedelta(minutes=135)),
    )

    payload, rows = MethodologyVariantBAlignmentIntegrity().calculate(
        observations,
        audits,
        _bars(start),
    )

    datasets = {row["Comparison Dataset"] for row in rows}
    assert datasets == {
        "STRICT_EXACT_COMPARISON",
        "EXPLORATORY_FORWARD_COMPARISON",
    }
    assert payload["counts"]["strict_exact_count"] == 1
    assert payload["counts"]["exploratory_forward_count"] == 1
    assert payload["decision_rule"][
        "active_gate_changes_permitted_from"
    ] == "STRICT_EXACT_COMPARISON_ONLY"


def test_reports_audit_reuse() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = (
        _observation(start + timedelta(minutes=100)),
        _observation(start + timedelta(minutes=110)),
    )
    audits = (_audit(start + timedelta(minutes=115)),)

    payload, rows = MethodologyVariantBAlignmentIntegrity().calculate(
        observations,
        audits,
        _bars(start),
    )

    assert len(rows) == 2
    assert all(row["Audit Reuse Count"] == 2 for row in rows)
    assert payload["counts"]["reused_audit_timestamp_count"] == 1
    assert payload["counts"]["shadow_rows_using_reused_audits"] == 2


def test_safety_flags_remain_false() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    payload, _ = MethodologyVariantBAlignmentIntegrity().calculate(
        (_observation(start + timedelta(minutes=100)),),
        (),
        _bars(start),
    )

    assert payload["trade_authority"] is False
    assert payload["active_pipeline_modified"] is False
