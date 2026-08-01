from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta

import pytest

from core.backtesting.methodology_condition_outcome_attribution import (
    MethodologyConditionOutcomeAttribution,
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


CONDITION = MethodologyCondition(
    code="TEST_CONDITION",
    description="Condition used for attribution tests.",
    required=True,
    evidence_reference="test_condition",
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
    methodology: MethodologyIdentifier,
    timestamp: datetime,
    *,
    state: str,
) -> MethodologyResult:
    if state == "SATISFIED":
        status = MethodologyEvaluationStatus.CONFIRMED
        satisfied = (CONDITION,)
        failed = ()
        unavailable = ()
    elif state == "FAILED":
        status = MethodologyEvaluationStatus.NOT_CONFIRMED
        satisfied = ()
        failed = (CONDITION,)
        unavailable = ()
    elif state == "UNAVAILABLE":
        status = MethodologyEvaluationStatus.INCOMPLETE
        satisfied = ()
        failed = ()
        unavailable = (CONDITION,)
    else:
        raise ValueError("unsupported test state")

    return MethodologyResult(
        methodology=methodology,
        timestamp=timestamp,
        evaluation_status=status,
        direction=MethodologyDirection.BULLISH,
        satisfied_conditions=satisfied,
        failed_conditions=failed,
        unavailable_conditions=unavailable,
        reason_codes=(f"{methodology.value}_{state}",),
        reason="Deterministic attribution test result.",
    )


def _observation(timestamp: datetime, *, smc_state: str) -> MethodologyObservation:
    return MethodologyObservation(
        timestamp=timestamp,
        context=_context(timestamp),
        smc=_result(
            MethodologyIdentifier.SMC,
            timestamp,
            state=smc_state,
        ),
        ict=_result(
            MethodologyIdentifier.ICT,
            timestamp,
            state="FAILED",
        ),
    )


def _evaluation(
    timestamp: datetime,
    *,
    methodology: MethodologyIdentifier,
    favorable: bool,
    return_percent: float,
    horizon: int = 12,
) -> MethodologyOutcomeEvaluation:
    return MethodologyOutcomeEvaluation(
        observation_timestamp=timestamp,
        methodology=methodology,
        evaluation_status=(
            MethodologyEvaluationStatus.CONFIRMED
            if favorable
            else MethodologyEvaluationStatus.NOT_CONFIRMED
        ),
        direction=MethodologyDirection.BULLISH,
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


def test_attributes_satisfied_failed_and_unavailable_states() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = (
        _observation(start, smc_state="SATISFIED"),
        _observation(start + timedelta(minutes=5), smc_state="FAILED"),
        _observation(start + timedelta(minutes=10), smc_state="UNAVAILABLE"),
    )
    evaluations = (
        _evaluation(
            start,
            methodology=MethodologyIdentifier.SMC,
            favorable=True,
            return_percent=2.0,
        ),
        _evaluation(
            start + timedelta(minutes=5),
            methodology=MethodologyIdentifier.SMC,
            favorable=False,
            return_percent=-1.0,
        ),
        _evaluation(
            start + timedelta(minutes=10),
            methodology=MethodologyIdentifier.SMC,
            favorable=True,
            return_percent=0.5,
        ),
    )
    analytics = MethodologyConditionOutcomeAttribution(
        fold_count=2,
        minimum_sample_size=1,
    )

    payload, rows = analytics.calculate(observations, evaluations)

    row = next(
        item
        for item in rows
        if item["Methodology"] == "SMC"
        and item["Condition Code"] == "TEST_CONDITION"
    )
    assert row["Satisfied Sample Count"] == 1
    assert row["Failed Sample Count"] == 1
    assert row["Unavailable Sample Count"] == 1
    assert row["Favorable Rate Delta"] == 1.0
    assert row["Average Return Delta Percent"] == 3.0
    assert payload["observational_only"] is True
    assert payload["trade_authority"] is False


def test_fold_stability_counts_positive_deltas() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = []
    evaluations = []
    for index in range(4):
        timestamp = start + timedelta(minutes=5 * index)
        state = "SATISFIED" if index % 2 == 0 else "FAILED"
        observations.append(_observation(timestamp, smc_state=state))
        evaluations.append(
            _evaluation(
                timestamp,
                methodology=MethodologyIdentifier.SMC,
                favorable=state == "SATISFIED",
                return_percent=1.0 if state == "SATISFIED" else -1.0,
            )
        )
    analytics = MethodologyConditionOutcomeAttribution(
        fold_count=2,
        minimum_sample_size=1,
    )

    payload, _ = analytics.calculate(tuple(observations), tuple(evaluations))

    summary = next(
        item
        for item in payload["stability_summary"]
        if item["Methodology"] == "SMC"
        and item["Condition Code"] == "TEST_CONDITION"
    )
    assert summary["Valid Fold Count"] == 2
    assert summary["Positive Favorable Delta Folds"] == 2
    assert summary["Positive Return Delta Folds"] == 2
    assert summary["Stability Warnings"] == []


def test_export_writes_csv_json_and_window_metadata(tmp_path) -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    analytics = MethodologyConditionOutcomeAttribution(
        tmp_path,
        fold_count=2,
        minimum_sample_size=1,
    )

    csv_path, json_path = analytics.export(
        (
            _observation(timestamp, smc_state="SATISFIED"),
            _observation(
                timestamp + timedelta(minutes=5),
                smc_state="FAILED",
            ),
        ),
        (
            _evaluation(
                timestamp,
                methodology=MethodologyIdentifier.SMC,
                favorable=True,
                return_percent=1.0,
            ),
            _evaluation(
                timestamp + timedelta(minutes=5),
                methodology=MethodologyIdentifier.SMC,
                favorable=False,
                return_percent=-1.0,
            ),
        ),
        window_metadata={"requested_end_time": "2026-01-01T00:00:00+00:00"},
    )

    with csv_path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert rows
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["window_metadata"]["requested_end_time"] == (
        "2026-01-01T00:00:00+00:00"
    )
    assert payload["future_information_used_for_research_only"] is True


def test_rejects_unmatched_outcome_key() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    observation = _observation(timestamp, smc_state="SATISFIED")
    evaluation = _evaluation(
        timestamp + timedelta(minutes=5),
        methodology=MethodologyIdentifier.SMC,
        favorable=True,
        return_percent=1.0,
    )

    with pytest.raises(ValueError, match="without matching"):
        MethodologyConditionOutcomeAttribution().calculate(
            (observation,),
            (evaluation,),
        )


def test_empty_input_is_valid(tmp_path) -> None:
    csv_path, json_path = MethodologyConditionOutcomeAttribution(
        tmp_path
    ).export((), ())

    with csv_path.open(newline="", encoding="utf-8") as file:
        assert list(csv.DictReader(file)) == []
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["aggregate_comparisons"] == []
    assert payload["fold_comparisons"] == []
    assert payload["stability_summary"] == []
