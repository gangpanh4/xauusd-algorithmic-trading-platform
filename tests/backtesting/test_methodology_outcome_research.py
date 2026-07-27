from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta

import pytest

from core.backtesting.methodology_observer import MethodologyObservation
from core.backtesting.methodology_outcome_research import (
    MethodologyOutcomeResearch,
)
from core.multi_timeframe.enums import MarketBias
from core.regime_detector.models import MarketBar
from core.strategies.methodology_models import (
    MethodologyCondition,
    MethodologyDirection,
    MethodologyEvaluationStatus,
    MethodologyIdentifier,
    MethodologyResult,
)
from core.strategies.smc_ict_context import PriceLocation, SMCICTContext


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
    direction: MethodologyDirection,
    status: MethodologyEvaluationStatus,
) -> MethodologyResult:
    condition = MethodologyCondition(
        code=f"{methodology.value}_RULE",
        description="Research condition.",
    )
    if status is MethodologyEvaluationStatus.CONFIRMED:
        satisfied, failed = (condition,), ()
    else:
        satisfied, failed = (), (condition,)
    return MethodologyResult(
        methodology=methodology,
        timestamp=timestamp,
        evaluation_status=status,
        direction=direction,
        satisfied_conditions=satisfied,
        failed_conditions=failed,
        reason_codes=(f"{methodology.value}_{status.value}",),
        reason="Deterministic test result.",
    )


def _observation(timestamp: datetime) -> MethodologyObservation:
    return MethodologyObservation(
        timestamp=timestamp,
        context=_context(timestamp),
        smc=_result(
            MethodologyIdentifier.SMC,
            timestamp,
            MethodologyDirection.BULLISH,
            MethodologyEvaluationStatus.CONFIRMED,
        ),
        ict=_result(
            MethodologyIdentifier.ICT,
            timestamp,
            MethodologyDirection.BEARISH,
            MethodologyEvaluationStatus.NOT_CONFIRMED,
        ),
    )


def _bar(timestamp: datetime, *, high: float, low: float, close: float) -> MarketBar:
    return MarketBar(
        timestamp=timestamp,
        open=100.0,
        high=high,
        low=low,
        close=close,
        volume=1.0,
        tick_volume=1,
    )


def test_evaluates_bullish_and_bearish_fixed_horizons() -> None:
    timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    bars = (
        _bar(timestamp, high=101.0, low=99.0, close=100.0),
        _bar(timestamp + timedelta(minutes=5), high=102.0, low=99.0, close=101.0),
        _bar(timestamp + timedelta(minutes=10), high=103.0, low=98.0, close=102.0),
        _bar(timestamp + timedelta(minutes=15), high=104.0, low=97.0, close=103.0),
    )
    research = MethodologyOutcomeResearch(".", horizons=(1, 3))

    evaluations = research.evaluate((_observation(timestamp),), bars)

    assert len(evaluations) == 4
    smc_three = next(
        item
        for item in evaluations
        if item.methodology is MethodologyIdentifier.SMC
        and item.horizon_bars == 3
    )
    assert smc_three.directional_move == 3.0
    assert smc_three.maximum_favorable_excursion == 4.0
    assert smc_three.maximum_adverse_excursion == 3.0
    assert smc_three.favorable_terminal_outcome is True

    ict_three = next(
        item
        for item in evaluations
        if item.methodology is MethodologyIdentifier.ICT
        and item.horizon_bars == 3
    )
    assert ict_three.directional_move == -3.0
    assert ict_three.maximum_favorable_excursion == 3.0
    assert ict_three.maximum_adverse_excursion == 4.0
    assert ict_three.favorable_terminal_outcome is False


def test_bars_at_observation_timestamp_are_not_future_information() -> None:
    timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    bars = (
        _bar(timestamp, high=150.0, low=50.0, close=140.0),
        _bar(timestamp + timedelta(minutes=5), high=101.0, low=99.0, close=101.0),
    )

    evaluations = MethodologyOutcomeResearch(".", horizons=(1,)).evaluate(
        (_observation(timestamp),),
        bars,
    )

    assert all(item.terminal_price == 101.0 for item in evaluations)
    assert all(item.terminal_timestamp == bars[1].timestamp for item in evaluations)


def test_marks_tail_horizons_incomplete_without_fabricated_metrics() -> None:
    timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    bars = (
        _bar(timestamp, high=101.0, low=99.0, close=100.0),
        _bar(timestamp + timedelta(minutes=5), high=102.0, low=99.0, close=101.0),
    )

    evaluations = MethodologyOutcomeResearch(".", horizons=(3,)).evaluate(
        (_observation(timestamp),),
        bars,
    )

    assert len(evaluations) == 2
    assert all(item.horizon_complete is False for item in evaluations)
    assert all(item.directional_move is None for item in evaluations)


def test_exports_raw_outcomes_and_observational_summary(tmp_path) -> None:
    timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    bars = (
        _bar(timestamp, high=101.0, low=99.0, close=100.0),
        _bar(timestamp + timedelta(minutes=5), high=102.0, low=99.0, close=101.0),
    )
    research = MethodologyOutcomeResearch(tmp_path, horizons=(1,))
    evaluations = research.evaluate((_observation(timestamp),), bars)

    csv_path, json_path = research.export(evaluations)

    with csv_path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 2
    assert {row["Methodology"] for row in rows} == {"SMC", "ICT"}

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["total_evaluations"] == 2
    assert payload["complete_directional_evaluations"] == 2
    assert payload["observational_only"] is True
    assert payload["trade_authority"] is False
    assert payload["future_information_used_for_research_only"] is True


def test_rejects_non_monotonic_m5_bars() -> None:
    timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    bar = _bar(timestamp, high=101.0, low=99.0, close=100.0)

    with pytest.raises(ValueError, match="strictly increasing"):
        MethodologyOutcomeResearch(".").evaluate(
            (_observation(timestamp),),
            (bar, bar),
        )
