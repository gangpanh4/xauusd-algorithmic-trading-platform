from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta

import pytest

from core.backtesting.methodology_candidate_rule_simulator import (
    MethodologyCandidateRuleSimulator,
)
from core.backtesting.methodology_observer import MethodologyObservation
from core.backtesting.methodology_outcome_research import (
    MethodologyOutcomeEvaluation,
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
        current_bar_index=10,
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
    status: MethodologyEvaluationStatus,
    methodology: MethodologyIdentifier = MethodologyIdentifier.SMC,
) -> MethodologyResult:
    return MethodologyResult(
        methodology=methodology,
        timestamp=timestamp,
        evaluation_status=status,
        direction=direction,
        satisfied_conditions=tuple(_condition(code) for code in satisfied),
        failed_conditions=tuple(_condition(code) for code in failed),
        unavailable_conditions=(),
        reason_codes=("TEST",),
        reason="Candidate simulator test.",
    )


def _observation(
    timestamp: datetime,
    *,
    direction: MethodologyDirection,
    satisfied: tuple[str, ...],
    failed: tuple[str, ...],
    status: MethodologyEvaluationStatus,
) -> MethodologyObservation:
    return MethodologyObservation(
        timestamp=timestamp,
        context=_context(timestamp),
        smc=_result(
            timestamp,
            direction=direction,
            satisfied=satisfied,
            failed=failed,
            status=status,
        ),
        ict=_result(
            timestamp,
            direction=direction,
            satisfied=satisfied,
            failed=failed,
            status=status,
            methodology=MethodologyIdentifier.ICT,
        ),
    )


def _evaluation(
    timestamp: datetime,
    *,
    direction: MethodologyDirection,
    status: MethodologyEvaluationStatus,
    horizon: int,
    favorable: bool,
    return_percent: float,
) -> MethodologyOutcomeEvaluation:
    return MethodologyOutcomeEvaluation(
        observation_timestamp=timestamp,
        methodology=MethodologyIdentifier.SMC,
        evaluation_status=status,
        direction=direction,
        horizon_bars=horizon,
        horizon_complete=True,
        source_price=100.0,
        terminal_timestamp=timestamp + timedelta(minutes=5 * horizon),
        terminal_price=100.0 + return_percent,
        directional_move=return_percent,
        directional_return_pct=return_percent,
        maximum_favorable_excursion=max(return_percent, 0.0) + 1.0,
        maximum_adverse_excursion=1.0,
        favorable_terminal_outcome=favorable,
        session_name="London",
        regime_name="TRENDING_BULL",
    )


def test_simulates_both_frozen_variants() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = (
        _observation(
            start,
            direction=MethodologyDirection.BULLISH,
            satisfied=("ORDER_BLOCK_PRESENT", "STRUCTURE_EVENT_ALIGNED"),
            failed=(),
            status=MethodologyEvaluationStatus.CONFIRMED,
        ),
        _observation(
            start + timedelta(minutes=5),
            direction=MethodologyDirection.BULLISH,
            satisfied=("ORDER_BLOCK_PRESENT",),
            failed=("STRUCTURE_EVENT_ALIGNED",),
            status=MethodologyEvaluationStatus.NOT_CONFIRMED,
        ),
        _observation(
            start + timedelta(minutes=10),
            direction=MethodologyDirection.BEARISH,
            satisfied=("ORDER_BLOCK_PRESENT",),
            failed=("LIQUIDITY_SWEEP_COMPATIBLE",),
            status=MethodologyEvaluationStatus.NOT_CONFIRMED,
        ),
        _observation(
            start + timedelta(minutes=15),
            direction=MethodologyDirection.BEARISH,
            satisfied=("LIQUIDITY_SWEEP_COMPATIBLE",),
            failed=("ORDER_BLOCK_PRESENT",),
            status=MethodologyEvaluationStatus.NOT_CONFIRMED,
        ),
    )
    evaluations = (
        _evaluation(
            start,
            direction=MethodologyDirection.BULLISH,
            status=MethodologyEvaluationStatus.CONFIRMED,
            horizon=12,
            favorable=True,
            return_percent=2.0,
        ),
        _evaluation(
            start + timedelta(minutes=5),
            direction=MethodologyDirection.BULLISH,
            status=MethodologyEvaluationStatus.NOT_CONFIRMED,
            horizon=12,
            favorable=False,
            return_percent=-1.0,
        ),
        _evaluation(
            start + timedelta(minutes=10),
            direction=MethodologyDirection.BEARISH,
            status=MethodologyEvaluationStatus.NOT_CONFIRMED,
            horizon=12,
            favorable=True,
            return_percent=1.0,
        ),
        _evaluation(
            start + timedelta(minutes=15),
            direction=MethodologyDirection.BEARISH,
            status=MethodologyEvaluationStatus.NOT_CONFIRMED,
            horizon=12,
            favorable=False,
            return_percent=-2.0,
        ),
    )

    payload, _ = MethodologyCandidateRuleSimulator(
        fold_count=2,
        minimum_sample_size=1,
    ).calculate(observations, evaluations)

    bullish = next(
        item for item in payload["variants"]
        if item["variant"] == "VARIANT_A_BULLISH_ORDER_BLOCK_STRUCTURE"
    )
    bearish = next(
        item for item in payload["variants"]
        if item["variant"] == (
            "VARIANT_B_BEARISH_EXCLUDE_COMPATIBLE_SWEEP"
        )
    )
    bullish_12 = bullish["aggregate"]["horizons"][0]
    bearish_12 = bearish["aggregate"]["horizons"][0]
    assert bullish_12["sample_counts"]["VARIANT"] == 1
    assert bullish_12["variant_minus_baseline_favorable_delta"] == 0.5
    assert bearish_12["sample_counts"]["VARIANT"] == 1
    assert bearish_12["variant_minus_baseline_return_delta_percent"] == 1.5
    assert payload["trade_authority"] is False
    assert payload["active_pipeline_modified"] is False


def test_reports_retention_composition_and_folds() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = []
    evaluations = []
    for index in range(4):
        timestamp = start + timedelta(minutes=5 * index)
        variant = index % 2 == 0
        observations.append(
            _observation(
                timestamp,
                direction=MethodologyDirection.BULLISH,
                satisfied=(
                    ("ORDER_BLOCK_PRESENT", "STRUCTURE_EVENT_ALIGNED")
                    if variant
                    else ("ORDER_BLOCK_PRESENT",)
                ),
                failed=() if variant else ("STRUCTURE_EVENT_ALIGNED",),
                status=(
                    MethodologyEvaluationStatus.CONFIRMED
                    if variant
                    else MethodologyEvaluationStatus.NOT_CONFIRMED
                ),
            )
        )
        evaluations.append(
            _evaluation(
                timestamp,
                direction=MethodologyDirection.BULLISH,
                status=(
                    MethodologyEvaluationStatus.CONFIRMED
                    if variant
                    else MethodologyEvaluationStatus.NOT_CONFIRMED
                ),
                horizon=12,
                favorable=variant,
                return_percent=1.0 if variant else -1.0,
            )
        )

    payload, _ = MethodologyCandidateRuleSimulator(
        fold_count=2,
        minimum_sample_size=1,
    ).calculate(tuple(observations), tuple(evaluations))

    bullish = next(
        item for item in payload["variants"]
        if item["variant"] == "VARIANT_A_BULLISH_ORDER_BLOCK_STRUCTURE"
    )
    assert bullish["retention"]["variant_observation_count"] == 2
    assert bullish["retention"]["direction_baseline_observation_count"] == 4
    assert bullish["retention"]["variant_vs_direction_baseline_retention"] == 0.5
    assert bullish["composition"]["session_counts"] == {"London": 2}
    summary = bullish["stability"][0]
    assert summary["valid_fold_count"] == 2
    assert summary["positive_favorable_delta_folds"] == 2



def test_builds_chronological_folds_separately_for_each_direction() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = []
    evaluations = []

    for index in range(20):
        timestamp = start + timedelta(minutes=5 * index)
        direction = (
            MethodologyDirection.BULLISH
            if index % 2 == 0
            else MethodologyDirection.BEARISH
        )
        if direction is MethodologyDirection.BULLISH:
            satisfied = (
                "ORDER_BLOCK_PRESENT",
                "STRUCTURE_EVENT_ALIGNED",
            )
            failed = ()
            favorable = True
            return_percent = 1.0
            status = MethodologyEvaluationStatus.CONFIRMED
        else:
            satisfied = ("ORDER_BLOCK_PRESENT",)
            failed = ("LIQUIDITY_SWEEP_COMPATIBLE",)
            favorable = True
            return_percent = 1.0
            status = MethodologyEvaluationStatus.NOT_CONFIRMED

        observations.append(
            _observation(
                timestamp,
                direction=direction,
                satisfied=satisfied,
                failed=failed,
                status=status,
            )
        )
        evaluations.append(
            _evaluation(
                timestamp,
                direction=direction,
                status=status,
                horizon=12,
                favorable=favorable,
                return_percent=return_percent,
            )
        )

    payload, _ = MethodologyCandidateRuleSimulator(
        fold_count=5,
        minimum_sample_size=1,
    ).calculate(tuple(observations), tuple(evaluations))

    assert payload["fold_partitioning"] == (
        "DIRECTION_SPECIFIC_TIMESTAMPS"
    )

    bullish = next(
        item
        for item in payload["variants"]
        if item["direction"] == "BULLISH"
    )
    bearish = next(
        item
        for item in payload["variants"]
        if item["direction"] == "BEARISH"
    )

    assert bullish["fold_partitioning"] == {
        "basis": "DIRECTION_SPECIFIC_TIMESTAMPS",
        "direction_timestamp_count": 10,
        "requested_fold_count": 5,
        "fold_timestamp_counts": [2, 2, 2, 2, 2],
    }
    assert bearish["fold_partitioning"] == {
        "basis": "DIRECTION_SPECIFIC_TIMESTAMPS",
        "direction_timestamp_count": 10,
        "requested_fold_count": 5,
        "fold_timestamp_counts": [2, 2, 2, 2, 2],
    }

    for variant in (bullish, bearish):
        assert len(variant["folds"]) == 5
        assert all(
            fold["horizons"][0]["sample_counts"][
                "DIRECTION_BASELINE"
            ]
            == 2
            for fold in variant["folds"]
        )


def test_direction_specific_folds_preserve_directional_chronology() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = []
    evaluations = []

    bullish_offsets = (0, 1, 8, 9, 16, 17)
    bearish_offsets = (2, 3, 4, 5, 6, 7)

    for offset in sorted(bullish_offsets + bearish_offsets):
        timestamp = start + timedelta(minutes=5 * offset)
        bullish = offset in bullish_offsets
        direction = (
            MethodologyDirection.BULLISH
            if bullish
            else MethodologyDirection.BEARISH
        )
        satisfied = (
            ("ORDER_BLOCK_PRESENT", "STRUCTURE_EVENT_ALIGNED")
            if bullish
            else ("ORDER_BLOCK_PRESENT",)
        )
        failed = (
            ()
            if bullish
            else ("LIQUIDITY_SWEEP_COMPATIBLE",)
        )
        status = (
            MethodologyEvaluationStatus.CONFIRMED
            if bullish
            else MethodologyEvaluationStatus.NOT_CONFIRMED
        )
        observations.append(
            _observation(
                timestamp,
                direction=direction,
                satisfied=satisfied,
                failed=failed,
                status=status,
            )
        )
        evaluations.append(
            _evaluation(
                timestamp,
                direction=direction,
                status=status,
                horizon=12,
                favorable=True,
                return_percent=1.0,
            )
        )

    payload, _ = MethodologyCandidateRuleSimulator(
        fold_count=3,
        minimum_sample_size=1,
    ).calculate(tuple(observations), tuple(evaluations))

    bullish_variant = next(
        item
        for item in payload["variants"]
        if item["direction"] == "BULLISH"
    )
    bearish_variant = next(
        item
        for item in payload["variants"]
        if item["direction"] == "BEARISH"
    )

    assert bullish_variant["fold_partitioning"][
        "fold_timestamp_counts"
    ] == [2, 2, 2]
    assert bearish_variant["fold_partitioning"][
        "fold_timestamp_counts"
    ] == [2, 2, 2]

def test_export_writes_csv_json_and_window_metadata(tmp_path) -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    observation = _observation(
        timestamp,
        direction=MethodologyDirection.BULLISH,
        satisfied=("ORDER_BLOCK_PRESENT", "STRUCTURE_EVENT_ALIGNED"),
        failed=(),
        status=MethodologyEvaluationStatus.CONFIRMED,
    )
    evaluation = _evaluation(
        timestamp,
        direction=MethodologyDirection.BULLISH,
        status=MethodologyEvaluationStatus.CONFIRMED,
        horizon=12,
        favorable=True,
        return_percent=1.0,
    )

    csv_path, json_path = MethodologyCandidateRuleSimulator(
        tmp_path,
        fold_count=2,
        minimum_sample_size=1,
    ).export(
        (observation,),
        (evaluation,),
        window_metadata={"requested_end_time": "2026-07-27T23:59:00+00:00"},
    )

    with csv_path.open(newline="", encoding="utf-8") as file:
        assert list(csv.DictReader(file))
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["window_metadata"]["requested_end_time"] == (
        "2026-07-27T23:59:00+00:00"
    )
    assert payload["methodology_rules_modified"] is False


def test_empty_input_is_valid(tmp_path) -> None:
    csv_path, json_path = MethodologyCandidateRuleSimulator(
        tmp_path
    ).export((), ())

    with csv_path.open(newline="", encoding="utf-8") as file:
        assert list(csv.DictReader(file))
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["observation_count"] == 0
    assert len(payload["variants"]) == 2


def test_rejects_unmatched_outcome_timestamp() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    observation = _observation(
        timestamp,
        direction=MethodologyDirection.BULLISH,
        satisfied=("ORDER_BLOCK_PRESENT", "STRUCTURE_EVENT_ALIGNED"),
        failed=(),
        status=MethodologyEvaluationStatus.CONFIRMED,
    )
    evaluation = _evaluation(
        timestamp + timedelta(minutes=5),
        direction=MethodologyDirection.BULLISH,
        status=MethodologyEvaluationStatus.CONFIRMED,
        horizon=12,
        favorable=True,
        return_percent=1.0,
    )

    with pytest.raises(ValueError, match="without matching"):
        MethodologyCandidateRuleSimulator().calculate(
            (observation,),
            (evaluation,),
        )
