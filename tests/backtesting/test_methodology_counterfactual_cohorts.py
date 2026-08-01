from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta

import pytest

from core.backtesting.methodology_counterfactual_cohorts import (
    MethodologyCounterfactualCohorts,
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


def _context(
    timestamp: datetime,
    *,
    session: str = "London",
    regime: str | None = "TRENDING_BULL",
) -> SMCICTContext:
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
        session_name=session,
        regime_name=regime,
        missing_capabilities=(),
    )


def _result(
    timestamp: datetime,
    *,
    direction: MethodologyDirection,
    states: dict[str, str],
    methodology: MethodologyIdentifier = MethodologyIdentifier.SMC,
) -> MethodologyResult:
    satisfied = tuple(
        _condition(code)
        for code, state in states.items()
        if state == "SATISFIED"
    )
    failed = tuple(
        _condition(code)
        for code, state in states.items()
        if state == "FAILED"
    )
    unavailable = tuple(
        _condition(code)
        for code, state in states.items()
        if state == "UNAVAILABLE"
    )
    if unavailable:
        evaluation_status = MethodologyEvaluationStatus.INCOMPLETE
    elif failed:
        evaluation_status = MethodologyEvaluationStatus.NOT_CONFIRMED
    else:
        evaluation_status = MethodologyEvaluationStatus.CONFIRMED

    return MethodologyResult(
        methodology=methodology,
        timestamp=timestamp,
        evaluation_status=evaluation_status,
        direction=direction,
        satisfied_conditions=satisfied,
        failed_conditions=failed,
        unavailable_conditions=unavailable,
        reason_codes=("TEST",),
        reason="Counterfactual cohort test.",
    )


def _observation(
    timestamp: datetime,
    *,
    direction: MethodologyDirection,
    states: dict[str, str],
    session: str = "London",
    regime: str | None = "TRENDING_BULL",
) -> MethodologyObservation:
    return MethodologyObservation(
        timestamp=timestamp,
        context=_context(timestamp, session=session, regime=regime),
        smc=_result(timestamp, direction=direction, states=states),
        ict=_result(
            timestamp,
            direction=direction,
            states=states,
            methodology=MethodologyIdentifier.ICT,
        ),
    )


def _evaluation(
    timestamp: datetime,
    *,
    direction: MethodologyDirection,
    horizon: int,
    favorable: bool,
    return_percent: float,
) -> MethodologyOutcomeEvaluation:
    return MethodologyOutcomeEvaluation(
        observation_timestamp=timestamp,
        methodology=MethodologyIdentifier.SMC,
        evaluation_status=MethodologyEvaluationStatus.NOT_CONFIRMED,
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


def _states(*, order_block: str, liquidity: str) -> dict[str, str]:
    return {
        "ORDER_BLOCK_PRESENT": order_block,
        "LIQUIDITY_SWEEP_COMPATIBLE": liquidity,
        "FAIR_VALUE_GAP_PRESENT": "SATISFIED",
        "STRUCTURE_EVENT_ALIGNED": "SATISFIED",
    }


def test_calculates_frozen_bullish_and_bearish_cohorts() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = (
        _observation(
            start,
            direction=MethodologyDirection.BULLISH,
            states=_states(order_block="SATISFIED", liquidity="SATISFIED"),
        ),
        _observation(
            start + timedelta(minutes=5),
            direction=MethodologyDirection.BULLISH,
            states=_states(order_block="FAILED", liquidity="SATISFIED"),
        ),
        _observation(
            start + timedelta(minutes=10),
            direction=MethodologyDirection.BEARISH,
            states=_states(order_block="SATISFIED", liquidity="SATISFIED"),
        ),
        _observation(
            start + timedelta(minutes=15),
            direction=MethodologyDirection.BEARISH,
            states=_states(order_block="SATISFIED", liquidity="FAILED"),
        ),
    )
    evaluations = (
        _evaluation(
            start,
            direction=MethodologyDirection.BULLISH,
            horizon=12,
            favorable=True,
            return_percent=2.0,
        ),
        _evaluation(
            start + timedelta(minutes=5),
            direction=MethodologyDirection.BULLISH,
            horizon=12,
            favorable=False,
            return_percent=-1.0,
        ),
        _evaluation(
            start + timedelta(minutes=10),
            direction=MethodologyDirection.BEARISH,
            horizon=12,
            favorable=False,
            return_percent=-2.0,
        ),
        _evaluation(
            start + timedelta(minutes=15),
            direction=MethodologyDirection.BEARISH,
            horizon=12,
            favorable=True,
            return_percent=1.0,
        ),
    )
    analytics = MethodologyCounterfactualCohorts(
        fold_count=2,
        minimum_sample_size=1,
    )

    payload, rows = analytics.calculate(observations, evaluations)

    bullish = next(
        row
        for row in rows
        if row["Candidate"] == "BULLISH_ORDER_BLOCK_PRESENT"
        and row["Comparison Scope"] == "AGGREGATE"
        and row["Horizon Bars"] == 12
    )
    bearish = next(
        row
        for row in rows
        if row["Candidate"] == "BEARISH_LIQUIDITY_SWEEP_COMPATIBLE"
        and row["Comparison Scope"] == "AGGREGATE"
        and row["Horizon Bars"] == 12
    )
    assert bullish["Favorable Rate Delta"] == 1.0
    assert bullish["Average Return Delta Percent"] == 3.0
    assert bearish["Favorable Rate Delta"] == -1.0
    assert bearish["Average Return Delta Percent"] == -3.0
    assert payload["trade_authority"] is False
    assert payload["methodology_rules_modified"] is False


def test_reports_fold_stability_and_stratified_controls() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = []
    evaluations = []
    for index in range(8):
        timestamp = start + timedelta(minutes=5 * index)
        present = index % 2 == 0
        observations.append(
            _observation(
                timestamp,
                direction=MethodologyDirection.BULLISH,
                states=_states(
                    order_block="SATISFIED" if present else "FAILED",
                    liquidity="SATISFIED",
                ),
            )
        )
        evaluations.append(
            _evaluation(
                timestamp,
                direction=MethodologyDirection.BULLISH,
                horizon=12,
                favorable=present,
                return_percent=1.0 if present else -1.0,
            )
        )

    payload, rows = MethodologyCounterfactualCohorts(
        fold_count=2,
        minimum_sample_size=1,
    ).calculate(tuple(observations), tuple(evaluations))

    candidate = next(
        item
        for item in payload["candidates"]
        if item["candidate"] == "BULLISH_ORDER_BLOCK_PRESENT"
    )
    summary = next(
        item
        for item in candidate["stability_summary"]
        if item["horizon_bars"] == 12
    )
    assert summary["valid_fold_count"] == 2
    assert summary["positive_favorable_delta_folds"] == 2
    assert summary["positive_return_delta_folds"] == 2
    assert any(
        row["Comparison Scope"] == "STRATIFIED"
        and row["Control Condition"] == "LIQUIDITY_SWEEP_COMPATIBLE"
        and row["Control State"] == "SATISFIED"
        for row in rows
    )


def test_reports_session_regime_and_overlap_composition() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    observation = _observation(
        timestamp,
        direction=MethodologyDirection.BULLISH,
        states=_states(order_block="SATISFIED", liquidity="SATISFIED"),
        session="NewYork",
        regime=None,
    )
    evaluation = _evaluation(
        timestamp,
        direction=MethodologyDirection.BULLISH,
        horizon=12,
        favorable=True,
        return_percent=1.0,
    )

    payload, _ = MethodologyCounterfactualCohorts(
        fold_count=2,
        minimum_sample_size=1,
    ).calculate((observation,), (evaluation,))

    candidate = next(
        item
        for item in payload["candidates"]
        if item["candidate"] == "BULLISH_ORDER_BLOCK_PRESENT"
    )
    assert candidate["composition"]["PRESENT"]["session_counts"] == {
        "NewYork": 1
    }
    assert candidate["composition"]["PRESENT"]["regime_counts"] == {
        "MISSING": 1
    }
    overlap = next(
        item
        for item in candidate["overlap_rates"]
        if item["cohort"] == "PRESENT"
        and item["control_condition"] == "LIQUIDITY_SWEEP_COMPATIBLE"
    )
    assert overlap["control_satisfied_rate"] == 1.0


def test_export_writes_csv_json_and_window_metadata(tmp_path) -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    analytics = MethodologyCounterfactualCohorts(
        tmp_path,
        fold_count=2,
        minimum_sample_size=1,
    )
    csv_path, json_path = analytics.export(
        (
            _observation(
                timestamp,
                direction=MethodologyDirection.BULLISH,
                states=_states(
                    order_block="SATISFIED",
                    liquidity="SATISFIED",
                ),
            ),
        ),
        (
            _evaluation(
                timestamp,
                direction=MethodologyDirection.BULLISH,
                horizon=12,
                favorable=True,
                return_percent=1.0,
            ),
        ),
        window_metadata={"requested_end_time": "2026-07-27T23:59:00+00:00"},
    )

    with csv_path.open(newline="", encoding="utf-8") as file:
        assert list(csv.DictReader(file))
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["window_metadata"]["requested_end_time"] == (
        "2026-07-27T23:59:00+00:00"
    )
    assert payload["observational_only"] is True


def test_rejects_unmatched_outcome_timestamp() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    observation = _observation(
        timestamp,
        direction=MethodologyDirection.BULLISH,
        states=_states(order_block="SATISFIED", liquidity="SATISFIED"),
    )
    evaluation = _evaluation(
        timestamp + timedelta(minutes=5),
        direction=MethodologyDirection.BULLISH,
        horizon=12,
        favorable=True,
        return_percent=1.0,
    )

    with pytest.raises(ValueError, match="without matching"):
        MethodologyCounterfactualCohorts().calculate(
            (observation,),
            (evaluation,),
        )
