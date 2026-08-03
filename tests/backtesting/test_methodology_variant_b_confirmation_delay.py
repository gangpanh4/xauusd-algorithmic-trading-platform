from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from core.backtesting.methodology_observer import MethodologyObservation
from core.backtesting.methodology_variant_b_confirmation_delay import (
    MethodologyVariantBConfirmationDelay,
)
from core.multi_timeframe.enums import MarketBias
from core.strategies.methodology_models import (
    MethodologyCondition,
    MethodologyDirection,
    MethodologyEvaluationStatus,
    MethodologyIdentifier,
    MethodologyResult,
)
from core.strategies.smc_ict_context import (
    PriceLocation,
    SMCICTContext,
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
        evaluation_status=(
            MethodologyEvaluationStatus.NOT_CONFIRMED
        ),
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


def _bars(
    start: datetime,
    count: int = 120,
) -> tuple[_Bar, ...]:
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


def test_exports_six_causal_rules() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = tuple(
        _observation(start + timedelta(minutes=value))
        for value in (100, 105, 110, 140)
    )

    payload, rows = MethodologyVariantBConfirmationDelay().calculate(
        observations,
        _bars(start),
    )

    assert len(rows) == 6
    assert all(row["Causal"] is True for row in rows)
    assert payload["frozen_scenario"] == {
        "stop_atr_multiple": 1.0,
        "target_r": 2.0,
    }


def test_quiet_confirmation_shifts_timestamp() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = tuple(
        _observation(start + timedelta(minutes=value))
        for value in (100, 105, 120)
    )
    study = MethodologyVariantBConfirmationDelay()

    confirmed = study._quiet_confirmation(observations, 5)

    assert [item.timestamp for item, _ in confirmed] == [
        start + timedelta(minutes=110),
        start + timedelta(minutes=125),
    ]


def test_persistence_confirms_once_per_sequence() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = tuple(
        _observation(start + timedelta(minutes=value))
        for value in (100, 105, 110, 115, 140, 145)
    )
    study = MethodologyVariantBConfirmationDelay()

    confirmed = study._persistence(observations, 2)

    assert [item.timestamp for item, _ in confirmed] == [
        start + timedelta(minutes=105),
        start + timedelta(minutes=145),
    ]


def test_safety_flags_remain_false() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    payload, _ = MethodologyVariantBConfirmationDelay().calculate(
        (_observation(start + timedelta(minutes=100)),),
        _bars(start),
    )

    assert payload["trade_authority"] is False
    assert payload["active_pipeline_modified"] is False
