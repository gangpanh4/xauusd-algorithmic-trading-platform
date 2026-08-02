from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from core.backtesting.methodology_observer import MethodologyObservation
from core.backtesting.methodology_variant_b_cluster_selection import (
    MethodologyVariantBClusterSelection,
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


def test_exports_five_predeclared_rules() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = tuple(
        _observation(start + timedelta(minutes=value))
        for value in (100, 105, 110, 140)
    )

    payload, rows = MethodologyVariantBClusterSelection().calculate(
        observations,
        _bars(start),
    )

    assert len(rows) == 5
    assert payload["frozen_scenario"] == {
        "stop_atr_multiple": 1.0,
        "target_r": 2.0,
    }
    assert payload["unsupported_rules"][0]["rule"] == "BEST_SCORE_IN_CLUSTER"


def test_cluster_first_and_last_are_distinct() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = tuple(
        _observation(start + timedelta(minutes=value))
        for value in (100, 105, 110, 140)
    )
    study = MethodologyVariantBClusterSelection()

    first = study._first_in_cluster(observations)
    last = study._last_in_cluster(observations)

    assert [item.timestamp for item in first] == [
        observations[0].timestamp,
        observations[3].timestamp,
    ]
    assert [item.timestamp for item in last] == [
        observations[2].timestamp,
        observations[3].timestamp,
    ]


def test_marks_retrospective_rule_noncausal() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    payload, rows = MethodologyVariantBClusterSelection().calculate(
        (_observation(start + timedelta(minutes=100)),),
        _bars(start),
    )

    last = next(
        row for row in rows if row["Rule"] == "LAST_IN_15_MINUTE_CLUSTER"
    )
    assert last["Causal"] is False
    assert payload["trade_authority"] is False
    assert payload["active_pipeline_modified"] is False
