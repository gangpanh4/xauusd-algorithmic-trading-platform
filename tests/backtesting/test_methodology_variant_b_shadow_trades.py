from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from core.backtesting.config import BacktestConfig
from core.backtesting.methodology_variant_b_shadow_trades import (
    MethodologyVariantBShadowTrades,
)
from core.backtesting.methodology_observer import MethodologyObservation
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
    direction: MethodologyDirection,
    *,
    sweep_failed: bool,
    methodology: MethodologyIdentifier,
) -> MethodologyResult:
    failed = (
        (_condition("LIQUIDITY_SWEEP_COMPATIBLE"),)
        if sweep_failed
        else (_condition("OTHER_REQUIRED_CONDITION"),)
    )
    return MethodologyResult(
        methodology=methodology,
        timestamp=timestamp,
        evaluation_status=MethodologyEvaluationStatus.NOT_CONFIRMED,
        direction=direction,
        satisfied_conditions=(),
        failed_conditions=failed,
        unavailable_conditions=(),
        reason_codes=("TEST",),
        reason="test",
    )


def _observation(
    timestamp: datetime,
    *,
    direction: MethodologyDirection = MethodologyDirection.BEARISH,
    sweep_failed: bool = True,
) -> MethodologyObservation:
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
        smc=_result(
            timestamp,
            direction,
            sweep_failed=sweep_failed,
            methodology=MethodologyIdentifier.SMC,
        ),
        ict=_result(
            timestamp,
            direction,
            sweep_failed=sweep_failed,
            methodology=MethodologyIdentifier.ICT,
        ),
    )


def test_uses_only_frozen_variant_b_candidates() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = (
        _observation(start, direction=MethodologyDirection.BULLISH),
        _observation(start + timedelta(minutes=5), sweep_failed=False),
        _observation(start + timedelta(minutes=10)),
    )
    bars = tuple(
        _Bar(
            start + timedelta(minutes=5 * index),
            100.0,
            100.5,
            99.5,
            100.0,
        )
        for index in range(40)
    )

    payload, _ = MethodologyVariantBShadowTrades(
        BacktestConfig()
    ).calculate(observations, bars)

    assert payload["candidate_count"] == 1
    assert payload["trade_authority"] is False
    assert payload["active_pipeline_modified"] is False


def test_next_bar_entry_and_conservative_stop_first() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observation = _observation(start)
    bars = (
        _Bar(start, 100.0, 100.1, 99.9, 100.0),
        _Bar(
            start + timedelta(minutes=5),
            100.0,
            103.0,
            97.0,
            100.0,
        ),
    )

    payload, trades = MethodologyVariantBShadowTrades(
        BacktestConfig()
    ).calculate((observation,), bars)

    scenario = next(
        item
        for item in payload["scenarios"]
        if item["target_r"] == 1.0
    )
    trade = next(item for item in trades if item.target_r == 1.0)

    assert trade.entry_timestamp == start + timedelta(minutes=5)
    assert trade.exit_reason == "STOP_LOSS"
    assert trade.gross_r == -1.0
    assert scenario["executed_shadow_trade_count"] == 1


def test_exports_zero_cost_research_scenario(tmp_path) -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    bars = tuple(
        _Bar(
            start + timedelta(minutes=5 * index),
            100.0,
            100.2,
            97.0 if index == 1 else 99.8,
            99.0,
        )
        for index in range(30)
    )
    simulator = MethodologyVariantBShadowTrades(
        BacktestConfig(),
        tmp_path,
    )

    csv_path, json_path = simulator.export(
        (_observation(start),),
        bars,
        window_metadata={"window": "test"},
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert csv_path.exists()
    assert payload["execution_economics"]["classification"] == (
        "ZERO_COST_RESEARCH_SCENARIO"
    )
    assert payload["window_metadata"] == {"window": "test"}
    assert payload["future_information_used_for_research_only"] is True
