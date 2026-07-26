from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from core.data.models import MarketBar
from core.fair_value_gap_detector.enums import FairValueGapType
from core.fair_value_gap_detector.models import FairValueGapCandidate
from core.market_structure.enums import (
    BreakType,
    MarketTrend,
    OrderBlockType,
    SwingType,
    TrendDirection,
)
from core.market_structure.models import (
    BOSEvent,
    LiquidityLevel,
    LiquiditySweepEvent,
    StructureState,
    SwingPoint,
)
from core.multi_timeframe.enums import MarketBias, Timeframe
from core.order_block_detector.models import OrderBlock
from core.strategies.methodology_models import (
    MethodologyDirection,
    MethodologyEvaluationStatus,
    MethodologyIdentifier,
)
from core.strategies.smc_ict_context import PriceLocation, SMCICTContext
from core.strategies.smc_methodology import SMCMethodologyEvaluator


NOW = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)


def _bar(minutes: int, close: float = 2400.0) -> MarketBar:
    return MarketBar(
        timestamp=NOW + timedelta(minutes=minutes),
        open=close - 1.0,
        high=close + 2.0,
        low=close - 2.0,
        close=close,
        tick_volume=1,
    )


def _swing(
    *,
    direction: TrendDirection,
    confirmation_index: int = 8,
) -> SwingPoint:
    return SwingPoint(
        timestamp=NOW - timedelta(minutes=15),
        index=confirmation_index - 2,
        price=2390.0 if direction is TrendDirection.BULLISH else 2410.0,
        swing_type=(
            SwingType.HIGH
            if direction is TrendDirection.BULLISH
            else SwingType.LOW
        ),
        confirmation_index=confirmation_index,
    )


def _event(direction: TrendDirection) -> BOSEvent:
    return BOSEvent(
        timestamp=NOW - timedelta(minutes=5),
        break_type=BreakType.BOS,
        direction=direction,
        swing_point=_swing(direction=direction),
        break_price=2402.0,
        confirmation_index=10,
    )


def _swept_level(direction: TrendDirection) -> LiquidityLevel:
    # Bullish SMC interpretation expects a sell-side sweep.
    is_buy_side = direction is TrendDirection.BEARISH
    return LiquidityLevel(
        timestamp=NOW - timedelta(minutes=15),
        price=2410.0 if is_buy_side else 2390.0,
        swing_point=SwingPoint(
            timestamp=NOW - timedelta(minutes=20),
            index=6,
            price=2410.0 if is_buy_side else 2390.0,
            swing_type=SwingType.HIGH if is_buy_side else SwingType.LOW,
            confirmation_index=8,
        ),
        is_buy_side=is_buy_side,
    )


def _sweep(direction: TrendDirection) -> LiquiditySweepEvent:
    level = _swept_level(direction)
    return LiquiditySweepEvent(
        timestamp=NOW - timedelta(minutes=5),
        liquidity_level=level,
        sweep_price=level.price,
        confirmation_index=10,
    )


def _opposing_level(direction: TrendDirection) -> LiquidityLevel:
    is_buy_side = direction is TrendDirection.BULLISH
    return LiquidityLevel(
        timestamp=NOW - timedelta(minutes=10),
        price=2415.0 if is_buy_side else 2385.0,
        swing_point=SwingPoint(
            timestamp=NOW - timedelta(minutes=15),
            index=6,
            price=2415.0 if is_buy_side else 2385.0,
            swing_type=SwingType.HIGH if is_buy_side else SwingType.LOW,
            confirmation_index=8,
        ),
        is_buy_side=is_buy_side,
    )


def _structure(
    direction: TrendDirection,
    *,
    event: BOSEvent | None = None,
    sweep: LiquiditySweepEvent | None = None,
    opposing: LiquidityLevel | None = None,
) -> StructureState:
    return StructureState(
        timestamp=NOW,
        current_bar_index=20,
        trend=(
            MarketTrend.BULLISH
            if direction is TrendDirection.BULLISH
            else MarketTrend.BEARISH
        ),
        last_bos=event,
        last_liquidity=sweep,
        tracked_liquidity_levels=(
            (opposing,) if opposing is not None else ()
        ),
    )


def _gap() -> FairValueGapCandidate:
    return FairValueGapCandidate(
        timestamp=NOW - timedelta(minutes=5),
        gap_type=FairValueGapType.BULLISH,
        top_price=2405.0,
        bottom_price=2402.0,
        first_bar=_bar(-15),
        middle_bar=_bar(-10),
        third_bar=_bar(-5),
    )


def _order_block(direction: TrendDirection) -> OrderBlock:
    event = _event(direction)
    return OrderBlock(
        timestamp=NOW - timedelta(minutes=5),
        block_type=(
            OrderBlockType.BULLISH
            if direction is TrendDirection.BULLISH
            else OrderBlockType.BEARISH
        ),
        top_price=2400.0,
        bottom_price=2395.0,
        origin_swing=event.swing_point,
        trigger_break=event,
        trigger_liquidity=None,
        creation_index=8,
        confirmation_index=10,
    )


def _context(
    direction: TrendDirection = TrendDirection.BULLISH,
    *,
    bias: MarketBias | None = None,
    event: BOSEvent | None | object = ...,
    sweep: LiquiditySweepEvent | None | object = ...,
    opposing: LiquidityLevel | None | object = ...,
    gap: FairValueGapCandidate | None = None,
    order_block: OrderBlock | None = None,
    missing_capabilities: tuple[str, ...] = (
        "dealing_range_price_location",
        "displacement_detection",
        "session_context",
        "market_regime",
    ),
) -> SMCICTContext:
    actual_event = _event(direction) if event is ... else event
    actual_sweep = _sweep(direction) if sweep is ... else sweep
    actual_opposing = _opposing_level(direction) if opposing is ... else opposing
    actual_bias = bias or (
        MarketBias.BULLISH
        if direction is TrendDirection.BULLISH
        else MarketBias.BEARISH
    )
    structure = _structure(
        direction,
        event=actual_event,
        sweep=actual_sweep,
        opposing=actual_opposing,
    )
    return SMCICTContext(
        timestamp=NOW,
        current_bar_index=20,
        current_price=2400.0,
        higher_timeframe_bias=actual_bias,
        h4_structure=structure,
        h1_structure=structure,
        m15_structure=structure,
        m5_structure=structure,
        latest_structure_event=actual_event,
        latest_liquidity_sweep=actual_sweep,
        opposing_liquidity_level=actual_opposing,
        active_fair_value_gap=gap,
        active_order_block=order_block,
        latest_structure_event_timeframe=(
            Timeframe.M15 if actual_event is not None else None
        ),
        latest_liquidity_sweep_timeframe=(
            Timeframe.M15 if actual_sweep is not None else None
        ),
        opposing_liquidity_timeframe=(
            Timeframe.M15 if actual_opposing is not None else None
        ),
        active_fair_value_gap_timeframe=(
            Timeframe.M15 if gap is not None else None
        ),
        active_order_block_timeframe=(
            Timeframe.M15 if order_block is not None else None
        ),
        price_location=PriceLocation.UNKNOWN,
        displacement_present=None,
        session_name=None,
        regime_name=None,
        missing_capabilities=missing_capabilities,
    )


def _codes(conditions) -> set[str]:
    return {condition.code for condition in conditions}


def test_confirms_bullish_smc_interpretation() -> None:
    result = SMCMethodologyEvaluator().evaluate(_context())

    assert result.methodology is MethodologyIdentifier.SMC
    assert result.evaluation_status is MethodologyEvaluationStatus.CONFIRMED
    assert result.direction is MethodologyDirection.BULLISH
    assert result.confidence is None
    assert result.reason_codes == ("SMC_CONFIRMED",)
    assert {
        "HTF_BIAS_ALIGNED",
        "STRUCTURE_EVENT_PRESENT",
        "STRUCTURE_EVENT_ALIGNED",
        "LIQUIDITY_SWEEP_PRESENT",
        "LIQUIDITY_SWEEP_COMPATIBLE",
        "OPPOSING_LIQUIDITY_PRESENT",
    }.issubset(_codes(result.satisfied_conditions))


def test_confirms_bearish_smc_interpretation() -> None:
    result = SMCMethodologyEvaluator().evaluate(
        _context(TrendDirection.BEARISH)
    )

    assert result.evaluation_status is MethodologyEvaluationStatus.CONFIRMED
    assert result.direction is MethodologyDirection.BEARISH


def test_neutral_htf_bias_is_not_confirmed() -> None:
    result = SMCMethodologyEvaluator().evaluate(
        _context(bias=MarketBias.NEUTRAL)
    )

    assert result.evaluation_status is MethodologyEvaluationStatus.NOT_CONFIRMED
    assert result.direction is MethodologyDirection.NEUTRAL
    assert "HTF_BIAS_ALIGNED" in _codes(result.failed_conditions)


def test_missing_structure_event_fails_presence_and_marks_alignment_unavailable() -> None:
    result = SMCMethodologyEvaluator().evaluate(_context(event=None))

    assert result.evaluation_status is MethodologyEvaluationStatus.NOT_CONFIRMED
    assert "STRUCTURE_EVENT_PRESENT" in _codes(result.failed_conditions)
    assert "STRUCTURE_EVENT_ALIGNED" in _codes(
        result.unavailable_conditions
    )


def test_structure_event_direction_conflict_fails_alignment() -> None:
    result = SMCMethodologyEvaluator().evaluate(
        _context(event=_event(TrendDirection.BEARISH))
    )

    assert result.evaluation_status is MethodologyEvaluationStatus.NOT_CONFIRMED
    assert "STRUCTURE_EVENT_ALIGNED" in _codes(result.failed_conditions)


def test_missing_sweep_fails_presence_and_marks_compatibility_unavailable() -> None:
    result = SMCMethodologyEvaluator().evaluate(_context(sweep=None))

    assert result.evaluation_status is MethodologyEvaluationStatus.NOT_CONFIRMED
    assert "LIQUIDITY_SWEEP_PRESENT" in _codes(result.failed_conditions)
    assert "LIQUIDITY_SWEEP_COMPATIBLE" in _codes(
        result.unavailable_conditions
    )


def test_incompatible_sweep_side_fails_rule() -> None:
    incompatible = _sweep(TrendDirection.BEARISH)
    result = SMCMethodologyEvaluator().evaluate(
        _context(sweep=incompatible)
    )

    assert result.evaluation_status is MethodologyEvaluationStatus.NOT_CONFIRMED
    assert "LIQUIDITY_SWEEP_COMPATIBLE" in _codes(
        result.failed_conditions
    )


def test_missing_opposing_liquidity_fails_rule() -> None:
    result = SMCMethodologyEvaluator().evaluate(_context(opposing=None))

    assert result.evaluation_status is MethodologyEvaluationStatus.NOT_CONFIRMED
    assert "OPPOSING_LIQUIDITY_PRESENT" in _codes(
        result.failed_conditions
    )


def test_optional_fvg_and_order_block_absence_does_not_block_confirmation() -> None:
    result = SMCMethodologyEvaluator().evaluate(
        _context(gap=None, order_block=None)
    )

    assert result.evaluation_status is MethodologyEvaluationStatus.CONFIRMED
    assert "FAIR_VALUE_GAP_PRESENT" in _codes(result.failed_conditions)
    assert "ORDER_BLOCK_PRESENT" in _codes(result.failed_conditions)
    assert all(
        not condition.required
        for condition in result.failed_conditions
        if condition.code in {
            "FAIR_VALUE_GAP_PRESENT",
            "ORDER_BLOCK_PRESENT",
        }
    )


def test_optional_fvg_and_order_block_presence_are_reported() -> None:
    result = SMCMethodologyEvaluator().evaluate(
        _context(
            gap=_gap(),
            order_block=_order_block(TrendDirection.BULLISH),
        )
    )

    assert "FAIR_VALUE_GAP_PRESENT" in _codes(
        result.satisfied_conditions
    )
    assert "ORDER_BLOCK_PRESENT" in _codes(
        result.satisfied_conditions
    )


def test_missing_capabilities_are_optional_unavailable_not_failed() -> None:
    result = SMCMethodologyEvaluator().evaluate(_context())

    unavailable = _codes(result.unavailable_conditions)
    assert {
        "PRICE_LOCATION_UNAVAILABLE",
        "DISPLACEMENT_UNAVAILABLE",
        "SESSION_CONTEXT_UNAVAILABLE",
        "MARKET_REGIME_UNAVAILABLE",
    }.issubset(unavailable)
    assert result.evaluation_status is MethodologyEvaluationStatus.CONFIRMED
    assert all(
        not condition.required
        for condition in result.unavailable_conditions
        if condition.code in unavailable
    )


def test_no_missing_capability_codes_when_capabilities_are_not_reported_missing() -> None:
    result = SMCMethodologyEvaluator().evaluate(
        _context(missing_capabilities=())
    )

    assert not {
        "PRICE_LOCATION_UNAVAILABLE",
        "DISPLACEMENT_UNAVAILABLE",
        "SESSION_CONTEXT_UNAVAILABLE",
        "MARKET_REGIME_UNAVAILABLE",
    } & _codes(result.unavailable_conditions)


def test_identical_context_produces_identical_result() -> None:
    context = _context()
    evaluator = SMCMethodologyEvaluator()

    assert evaluator.evaluate(context) == evaluator.evaluate(context)


def test_evaluator_rejects_wrong_input_type() -> None:
    with pytest.raises(TypeError, match="context must be SMCICTContext"):
        SMCMethodologyEvaluator().evaluate(object())


def test_result_is_observational_only() -> None:
    result = SMCMethodologyEvaluator().evaluate(_context())

    assert result.metadata["observational_only"] is True
    prohibited = {
        "entry_price",
        "stop_loss",
        "target_price",
        "position_size",
        "signal",
        "approved",
        "authorized",
        "execution_status",
    }
    assert prohibited.isdisjoint(type(result).__dataclass_fields__)


def test_module_does_not_import_runtime_authority_packages() -> None:
    import core.strategies.smc_methodology as module

    imported_modules = {
        value.__module__
        for value in vars(module).values()
        if isinstance(value, type)
    }
    prohibited_prefixes = (
        "core.trading_pipeline",
        "core.risk_manager",
        "core.live_trading",
        "core.mt5_execution",
        "core.signal_generator",
        "core.decision_engine",
        "core.trade_quality",
        "core.probability_engine",
    )
    assert not any(
        imported.startswith(prohibited_prefixes)
        for imported in imported_modules
    )
