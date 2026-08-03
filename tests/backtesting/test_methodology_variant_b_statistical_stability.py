from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from core.backtesting.methodology_observer import MethodologyObservation
from core.backtesting.methodology_variant_b_statistical_stability import (
    MethodologyVariantBStatisticalStability,
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


def _bars(start: datetime, count: int = 160) -> tuple[_Bar, ...]:
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


def test_exports_monthly_and_rolling_stability() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = tuple(
        _observation(start + timedelta(minutes=100 + index * 30))
        for index in range(6)
    )

    payload, rows = MethodologyVariantBStatisticalStability().calculate(
        observations,
        _bars(start),
    )

    assert payload["frozen_scenario"]["target_r"] == 2.0
    assert "monthly_summary" in payload
    assert "rolling_trade_blocks" in payload
    assert rows


def test_bootstrap_is_deterministic() -> None:
    study = MethodologyVariantBStatisticalStability()
    first = study._bootstrap_average_r([1.0, -1.0, 2.0, -0.5])
    second = study._bootstrap_average_r([1.0, -1.0, 2.0, -0.5])

    assert first == second
    assert first["bootstrap_samples"] == 2000


def test_losing_streak_and_drawdown_duration() -> None:
    study = MethodologyVariantBStatisticalStability()

    assert study._longest_losing_streak([1.0, -1.0, -1.0, 1.0]) == 2
    assert study._maximum_drawdown_duration([1.0, -0.5, -0.5, 1.0]) == 2


def test_safety_flags_remain_false() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    payload, _ = MethodologyVariantBStatisticalStability().calculate(
        (_observation(start + timedelta(minutes=100)),),
        _bars(start),
    )

    assert payload["trade_authority"] is False
    assert payload["active_pipeline_modified"] is False
