from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from core.backtesting.methodology_observer import MethodologyObservation
from core.backtesting.methodology_variant_b_execution_diagnostics import (
    MethodologyVariantBExecutionDiagnostics,
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


def _bars(start: datetime, count: int = 50) -> tuple[_Bar, ...]:
    values = []
    for index in range(count):
        base = 100.0 - index * 0.1
        values.append(
            _Bar(
                timestamp=start + timedelta(minutes=5 * index),
                open=base,
                high=base + 1.0,
                low=base - 1.5,
                close=base - 0.5,
            )
        )
    return tuple(values)


def test_exports_four_entry_delay_diagnostics(tmp_path) -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    diagnostic = MethodologyVariantBExecutionDiagnostics(tmp_path)

    csv_path, json_path = diagnostic.export(
        (_observation(start + timedelta(minutes=20)),),
        _bars(start),
        window_metadata={"window": "test"},
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert csv_path.exists()
    assert [item["entry_delay_bars"] for item in payload["delay_summaries"]] == [
        0,
        1,
        2,
        3,
    ]
    assert payload["candidate_count"] == 1
    assert payload["trade_authority"] is False
    assert payload["window_metadata"] == {"window": "test"}


def test_measures_r_reach_and_dual_touch() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    bars = list(_bars(start))
    entry_index = 6
    entry = bars[entry_index].open
    bars[entry_index] = _Bar(
        timestamp=bars[entry_index].timestamp,
        open=entry,
        high=entry + 3.0,
        low=entry - 3.0,
        close=entry - 1.0,
    )

    payload, rows = MethodologyVariantBExecutionDiagnostics().calculate(
        (_observation(start + timedelta(minutes=25)),),
        tuple(bars),
    )

    delay_zero = next(
        row
        for row in rows
        if row["Entry Delay Bars"] == 0
    )
    assert delay_zero["First 1.0R Bar"] == 1
    assert delay_zero["1.0R Same Candle Dual Touch"] is True
    assert payload["active_pipeline_modified"] is False


def test_atr_normalization_uses_only_pre_entry_bars() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    payload, rows = MethodologyVariantBExecutionDiagnostics().calculate(
        (_observation(start + timedelta(minutes=80)),),
        _bars(start, 60),
    )

    delay_zero = next(
        row
        for row in rows
        if row["Entry Delay Bars"] == 0
    )
    assert delay_zero["ATR 14"] is not None
    assert delay_zero["Stop Distance ATR Multiple"] is not None
    assert payload["future_information_used_for_research_only"] is True
