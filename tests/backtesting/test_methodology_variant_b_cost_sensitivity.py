from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from core.backtesting.methodology_observer import MethodologyObservation
from core.backtesting.methodology_variant_b_cost_sensitivity import (
    MethodologyVariantBCostSensitivity,
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
        regime_name="TRENDING_BEAR",
        missing_capabilities=(),
    )
    return MethodologyObservation(
        timestamp=timestamp,
        context=context,
        smc=_result(timestamp, MethodologyIdentifier.SMC),
        ict=_result(timestamp, MethodologyIdentifier.ICT),
    )


def _bars(start: datetime, count: int = 80) -> tuple[_Bar, ...]:
    return tuple(
        _Bar(
            timestamp=start + timedelta(minutes=5 * index),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
        )
        for index in range(count)
    )


def test_uses_only_two_frozen_scenarios() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    payload, rows = MethodologyVariantBCostSensitivity().calculate(
        (_observation(start + timedelta(minutes=100)),),
        _bars(start),
    )

    assert payload["frozen_scenarios"] == [
        {"stop_atr_multiple": 1.0, "target_r": 1.5},
        {"stop_atr_multiple": 1.0, "target_r": 2.0},
    ]
    assert len(rows) == 10
    assert {
        (row["Stop ATR Multiple"], row["Target R"])
        for row in rows
    } == {(1.0, 1.5), (1.0, 2.0)}


def test_costs_reduce_average_net_r_monotonically() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    _, rows = MethodologyVariantBCostSensitivity().calculate(
        (_observation(start + timedelta(minutes=100)),),
        _bars(start),
    )

    selected = [
        row
        for row in rows
        if row["Stop ATR Multiple"] == 1.0
        and row["Target R"] == 1.5
    ]
    averages = [row["Average Net R"] for row in selected]
    assert averages == sorted(averages, reverse=True)


def test_safety_flags_remain_false() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    payload, _ = MethodologyVariantBCostSensitivity().calculate(
        (_observation(start + timedelta(minutes=100)),),
        _bars(start),
    )

    assert payload["trade_authority"] is False
    assert payload["active_pipeline_modified"] is False
