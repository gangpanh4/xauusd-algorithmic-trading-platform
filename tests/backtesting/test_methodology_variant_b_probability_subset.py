from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from core.backtesting.methodology_observer import MethodologyObservation
from core.backtesting.methodology_variant_b_probability_subset import (
    MethodologyVariantBProbabilitySubset,
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


def _bars(start: datetime, count: int = 120) -> tuple[_Bar, ...]:
    values: list[_Bar] = []
    for index in range(count):
        values.append(
            _Bar(
                timestamp=start + timedelta(minutes=5 * index),
                open=100.0,
                high=103.0 if index >= 21 else 101.0,
                low=99.0,
                close=100.0,
            )
        )
    return tuple(values)


def _audit(
    timestamp: datetime,
    probability: float,
) -> PipelineObservationAudit:
    return PipelineObservationAudit(
        timestamp=timestamp,
        disposition=PipelineDisposition.REJECTED,
        stage_reached=PipelineStage.PROBABILITY,
        rejection_stage=PipelineStage.PROBABILITY,
        reason_code="PROBABILITY_REJECTED",
        reason="test",
        probability_calculated=True,
        probability_accepted=False,
        probability_value=probability,
    )


def test_uses_only_strict_exact_probability_rejections() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observation = _observation(start + timedelta(minutes=100))
    payload, _ = MethodologyVariantBProbabilitySubset().calculate(
        (observation,),
        (_audit(observation.timestamp, 0.35),),
        _bars(start),
    )

    assert payload["subset_counts"][
        "strict_exact_probability_rejected_count"
    ] == 1
    assert payload["subset_definition"]["alignment"] == (
        "STRICT_EXACT_TIMESTAMP_ONLY"
    )


def test_probability_band_assignment() -> None:
    study = MethodologyVariantBProbabilitySubset()

    assert study._band_label(0.35) == "[0.3,0.4)"
    assert study._band_label(1.0) == "[0.9,1.0)"


def test_bootstrap_is_deterministic() -> None:
    study = MethodologyVariantBProbabilitySubset()
    first = study._bootstrap([1.0, -1.0, 2.0])
    second = study._bootstrap([1.0, -1.0, 2.0])

    assert first == second
    assert first["bootstrap_samples"] == 2000


def test_safety_flags_remain_false() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    payload, _ = MethodologyVariantBProbabilitySubset().calculate(
        (_observation(start + timedelta(minutes=100)),),
        (),
        _bars(start),
    )

    assert payload["trade_authority"] is False
    assert payload["active_pipeline_modified"] is False


def test_exports_raw_strict_exact_trade_details(tmp_path) -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observation = _observation(start + timedelta(minutes=100))
    study = MethodologyVariantBProbabilitySubset(tmp_path)

    payload, _ = study.calculate(
        (observation,),
        (_audit(observation.timestamp, 0.55),),
        _bars(start),
        window_metadata={
            "requested_end_time": "2026-04-09T23:59:00+00:00",
            "actual": {
                "m5": {
                    "first_timestamp": "2025-12-24T10:05:00+00:00",
                    "last_timestamp": "2026-04-09T22:55:00+00:00",
                }
            },
        },
    )

    assert payload["detail_export"]["row_count"] == 1
    detail = payload["trade_details"][0]
    assert detail["Probability Band"] == "[0.5,0.6)"
    assert detail["Probability Value"] == 0.55
    assert detail["Net R Zero Cost"] == detail["Gross Result R"]
    assert detail["Requested End Time"] == (
        "2026-04-09T23:59:00+00:00"
    )


def test_export_writes_probability_subset_trade_csv(tmp_path) -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observation = _observation(start + timedelta(minutes=100))
    study = MethodologyVariantBProbabilitySubset(tmp_path)

    study.export(
        (observation,),
        (_audit(observation.timestamp, 0.55),),
        _bars(start),
    )

    detail_path = (
        tmp_path
        / "methodology_variant_b_probability_subset_trades.csv"
    )
    assert detail_path.exists()
    text = detail_path.read_text(encoding="utf-8")
    assert "Probability Value" in text
    assert "[0.5,0.6)" in text
