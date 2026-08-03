from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from core.backtesting.methodology_observer import MethodologyObservation
from core.backtesting.methodology_variant_b_shadow_integration import (
    MethodologyVariantBShadowIntegration,
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


def _bars(start: datetime, count: int = 100) -> tuple[_Bar, ...]:
    return tuple(
        _Bar(
            timestamp=start + timedelta(minutes=5 * index),
            open=100.0,
            high=101.0,
            low=98.0,
            close=99.0,
        )
        for index in range(count)
    )


def _rejected_audit(timestamp: datetime) -> PipelineObservationAudit:
    return PipelineObservationAudit(
        timestamp=timestamp,
        disposition=PipelineDisposition.REJECTED,
        stage_reached=PipelineStage.PROBABILITY,
        rejection_stage=PipelineStage.PROBABILITY,
        reason_code="PROBABILITY_REJECTED",
        reason="probability gate rejected",
        probability_calculated=True,
        probability_accepted=False,
        probability_value=0.40,
    )


def test_exports_shadow_plan_and_active_rejection_context() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observation = _observation(start + timedelta(minutes=100))
    audit = _rejected_audit(observation.timestamp)

    payload, rows = MethodologyVariantBShadowIntegration().calculate(
        (observation,),
        (audit,),
        _bars(start),
    )

    assert rows
    row = rows[0]
    assert row["Shadow Stop ATR Multiple"] == 1.0
    assert row["Shadow Target R"] == 2.0
    assert row["Active Reason Code"] == "PROBABILITY_REJECTED"
    assert (
        row["Comparison Classification"]
        == "SHADOW_ELIGIBLE_ACTIVE_REJECTED"
    )
    assert payload["trade_authority"] is False


def test_aligns_to_forward_audit_within_limit() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observation = _observation(start + timedelta(minutes=100))
    audit = _rejected_audit(
        observation.timestamp + timedelta(minutes=5)
    )

    _, rows = MethodologyVariantBShadowIntegration().calculate(
        (observation,),
        (audit,),
        _bars(start),
    )

    assert rows[0]["Alignment Method"] == "ASOF_FORWARD"
    assert rows[0]["Alignment Lag Minutes"] == 5.0


def test_marks_live_parity_not_ready() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observation = _observation(start + timedelta(minutes=100))

    payload, _ = MethodologyVariantBShadowIntegration().calculate(
        (observation,),
        (),
        _bars(start),
    )

    readiness = payload["backtest_live_parity_readiness"]
    assert readiness["status"] == "NOT_READY"
    assert readiness["active_trade_authority"] == "DISABLED"
    assert payload["active_pipeline_modified"] is False
