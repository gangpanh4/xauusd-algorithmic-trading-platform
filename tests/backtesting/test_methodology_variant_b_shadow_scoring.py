from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta

from core.backtesting.methodology_observer import MethodologyObservation
from core.backtesting.methodology_outcome_research import (
    MethodologyOutcomeEvaluation,
)
from core.backtesting.methodology_variant_b_shadow_scoring import (
    MethodologyVariantBShadowScoring,
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
        description=code,
        required=True,
        evidence_reference=code.lower(),
    )


def _context(timestamp: datetime) -> SMCICTContext:
    return SMCICTContext(
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
        regime_name="TRENDING_BEAR",
        missing_capabilities=(),
    )


def _result(
    timestamp: datetime,
    *,
    direction: MethodologyDirection,
    failed: tuple[str, ...],
    methodology: MethodologyIdentifier,
) -> MethodologyResult:
    effective_failed = failed or ("TEST_REQUIRED_CONDITION",)
    return MethodologyResult(
        methodology=methodology,
        timestamp=timestamp,
        evaluation_status=MethodologyEvaluationStatus.NOT_CONFIRMED,
        direction=direction,
        satisfied_conditions=(),
        failed_conditions=tuple(
            _condition(code)
            for code in effective_failed
        ),
        unavailable_conditions=(),
        reason_codes=("TEST",),
        reason="test",
    )


def _observation(
    timestamp: datetime,
    *,
    direction: MethodologyDirection,
    sweep_failed: bool,
) -> MethodologyObservation:
    failed = (
        ("LIQUIDITY_SWEEP_COMPATIBLE",)
        if sweep_failed
        else ()
    )
    return MethodologyObservation(
        timestamp=timestamp,
        context=_context(timestamp),
        smc=_result(
            timestamp,
            direction=direction,
            failed=failed,
            methodology=MethodologyIdentifier.SMC,
        ),
        ict=_result(
            timestamp,
            direction=direction,
            failed=failed,
            methodology=MethodologyIdentifier.ICT,
        ),
    )


def _audit(
    timestamp: datetime,
    *,
    accepted: bool = False,
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
        reason_code="PROBABILITY_REJECTED",
        reason="rejected",
    )


def _outcome(
    timestamp: datetime,
    *,
    favorable: bool,
    return_percent: float,
) -> MethodologyOutcomeEvaluation:
    return MethodologyOutcomeEvaluation(
        observation_timestamp=timestamp,
        methodology=MethodologyIdentifier.SMC,
        evaluation_status=MethodologyEvaluationStatus.NOT_CONFIRMED,
        direction=MethodologyDirection.BEARISH,
        horizon_bars=24,
        horizon_complete=True,
        source_price=100.0,
        terminal_timestamp=timestamp + timedelta(minutes=120),
        terminal_price=100.0 - return_percent,
        directional_move=return_percent,
        directional_return_pct=return_percent,
        maximum_favorable_excursion=max(return_percent, 0.0) + 1.0,
        maximum_adverse_excursion=1.0,
        favorable_terminal_outcome=favorable,
        session_name="London",
        regime_name="TRENDING_BEAR",
    )


def test_scores_only_frozen_variant_b_components() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = (
        _observation(
            start,
            direction=MethodologyDirection.BULLISH,
            sweep_failed=False,
        ),
        _observation(
            start + timedelta(minutes=5),
            direction=MethodologyDirection.BEARISH,
            sweep_failed=False,
        ),
        _observation(
            start + timedelta(minutes=10),
            direction=MethodologyDirection.BEARISH,
            sweep_failed=True,
        ),
    )
    audits = tuple(
        _audit(item.timestamp)
        for item in observations
    )
    outcomes = tuple(
        _outcome(
            item.timestamp,
            favorable=index != 1,
            return_percent=(1.0 if index != 1 else -1.0),
        )
        for index, item in enumerate(observations)
    )

    payload, rows = MethodologyVariantBShadowScoring().calculate(
        observations,
        audits,
        outcomes,
    )

    assert [row["Score"] for row in rows] == [0, 50, 100]
    assert [row["Research Cohort"] for row in rows] == [
        "OUT_OF_SCOPE_DIRECTION",
        "SCORE_50_BASELINE",
        "SCORE_100_VARIANT_B",
    ]
    assert payload["out_of_scope_direction"] == {
        "classification": "OUT_OF_SCOPE_DIRECTION",
        "sample_count": 1,
        "excluded_from_outcome_cohort_statistics": True,
        "active_accepted_count": 0,
    }
    assert rows[-1]["Variant B Eligible"] is True
    assert payload["component_weights"] == {
        "BEARISH_DIRECTION": 50,
        "LIQUIDITY_SWEEP_COMPATIBLE_FAILED": 50,
    }
    assert payload["trade_authority"] is False
    assert payload["signal_authority"] is False
    assert payload["approval_authority"] is False
    assert payload["position_sizing_authority"] is False


def test_summarizes_direction_conditioned_cohorts() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = (
        _observation(
            start,
            direction=MethodologyDirection.BEARISH,
            sweep_failed=True,
        ),
        _observation(
            start + timedelta(minutes=5),
            direction=MethodologyDirection.BEARISH,
            sweep_failed=True,
        ),
    )
    audits = (
        _audit(start),
        _audit(start + timedelta(minutes=5), accepted=True),
    )
    outcomes = (
        _outcome(start, favorable=True, return_percent=2.0),
        _outcome(
            start + timedelta(minutes=5),
            favorable=False,
            return_percent=-1.0,
        ),
    )

    payload, _ = MethodologyVariantBShadowScoring().calculate(
        observations,
        audits,
        outcomes,
    )

    variant_b = next(
        item
        for item in payload["cohorts"]
        if item["research_cohort"] == "SCORE_100_VARIANT_B"
    )
    assert variant_b["direction"] == "BEARISH"
    assert variant_b["sample_count"] == 2
    assert variant_b["complete_outcome_count"] == 2
    assert variant_b["outcome_coverage_rate"] == 1.0
    assert variant_b["favorable_rate"] == 0.5
    assert variant_b["average_directional_return_percent"] == 0.5
    assert variant_b["active_accepted_count"] == 1
    assert variant_b["active_rejection_reason_counts"] == {
        "PROBABILITY_REJECTED": 1
    }



def test_excludes_non_bearish_rows_from_cohort_statistics() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = (
        _observation(
            start,
            direction=MethodologyDirection.BULLISH,
            sweep_failed=True,
        ),
        _observation(
            start + timedelta(minutes=5),
            direction=MethodologyDirection.BEARISH,
            sweep_failed=False,
        ),
        _observation(
            start + timedelta(minutes=10),
            direction=MethodologyDirection.BEARISH,
            sweep_failed=True,
        ),
    )
    audits = tuple(_audit(item.timestamp) for item in observations)
    outcomes = tuple(
        _outcome(
            item.timestamp,
            favorable=True,
            return_percent=1.0,
        )
        for item in observations
    )

    payload, rows = MethodologyVariantBShadowScoring().calculate(
        observations,
        audits,
        outcomes,
    )

    assert len(rows) == 3
    assert payload["out_of_scope_direction"]["sample_count"] == 1
    assert sum(
        cohort["sample_count"]
        for cohort in payload["cohorts"]
    ) == 2
    assert {
        cohort["research_cohort"]
        for cohort in payload["cohorts"]
    } == {
        "SCORE_50_BASELINE",
        "SCORE_100_VARIANT_B",
    }


def test_exports_csv_and_json(tmp_path) -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    scorer = MethodologyVariantBShadowScoring(tmp_path)

    csv_path, json_path = scorer.export(
        (
            _observation(
                timestamp,
                direction=MethodologyDirection.BEARISH,
                sweep_failed=True,
            ),
        ),
        (_audit(timestamp),),
        (_outcome(timestamp, favorable=True, return_percent=1.0),),
        window_metadata={"requested_end_time": "2026-04-09"},
    )

    with csv_path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert len(rows) == 1
    assert rows[0]["Score"] == "100"
    assert rows[0]["Research Cohort"] == "SCORE_100_VARIANT_B"
    assert payload["window_metadata"] == {
        "requested_end_time": "2026-04-09"
    }
    assert payload["active_pipeline_modified"] is False
