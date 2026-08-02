from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from core.backtesting.methodology_observer import MethodologyObservation
from core.backtesting.methodology_variant_b_atr_shadow_matrix import (
    MethodologyVariantBATRShadowMatrix,
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


def test_builds_fixed_twelve_scenario_matrix(tmp_path) -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    matrix = MethodologyVariantBATRShadowMatrix(tmp_path)

    csv_path, json_path = matrix.export(
        (_observation(start + timedelta(minutes=100)),),
        _bars(start),
        window_metadata={"window": "test"},
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert csv_path.exists()
    assert len(payload["scenarios"]) == 12
    assert payload["stop_atr_multiples"] == [
        0.5,
        0.75,
        1.0,
        1.5,
    ]
    assert payload["target_r_multiples"] == [1.0, 1.5, 2.0]
    assert payload["trade_authority"] is False


def test_marks_same_candle_dual_touch_and_stops_first() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    bars = list(_bars(start))
    entry_index = 21
    bars[entry_index] = _Bar(
        timestamp=bars[entry_index].timestamp,
        open=100.0,
        high=103.0,
        low=97.0,
        close=100.0,
    )

    payload, results = MethodologyVariantBATRShadowMatrix().calculate(
        (_observation(start + timedelta(minutes=100)),),
        tuple(bars),
    )

    result = next(
        item
        for item in results
        if item.stop_atr_multiple == 0.5
        and item.target_r == 1.0
    )
    assert result.same_candle_dual_touch is True
    assert result.exit_reason == "AMBIGUOUS_STOP_FIRST"
    assert result.result_r == -1.0
    assert payload["active_pipeline_modified"] is False


def test_atr_uses_only_pre_entry_bars() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    payload, results = MethodologyVariantBATRShadowMatrix().calculate(
        (_observation(start + timedelta(minutes=100)),),
        _bars(start),
    )

    assert results
    assert all(result.atr_14 == 2.0 for result in results)
    assert payload["future_information_used_for_research_only"] is True
