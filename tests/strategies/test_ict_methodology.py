from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.data.models import MarketBar
from core.fair_value_gap_detector.enums import FairValueGapType
from core.fair_value_gap_detector.models import FairValueGapCandidate
from core.market_structure.enums import (
    BreakType,
    MarketTrend,
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
from core.strategies.ict_methodology import ICTMethodologyEvaluator
from core.strategies.methodology_models import (
    MethodologyDirection,
    MethodologyEvaluationStatus,
    MethodologyIdentifier,
)
from core.strategies.smc_ict_context import PriceLocation, SMCICTContext


NOW = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)


def _bar(minutes: int) -> MarketBar:
    return MarketBar(
        timestamp=NOW + timedelta(minutes=minutes),
        open=2399.0,
        high=2402.0,
        low=2398.0,
        close=2400.0,
        tick_volume=1,
    )


def _swing(direction: TrendDirection) -> SwingPoint:
    return SwingPoint(
        timestamp=NOW - timedelta(minutes=15),
        index=6,
        price=2390.0 if direction is TrendDirection.BULLISH else 2410.0,
        swing_type=(
            SwingType.HIGH
            if direction is TrendDirection.BULLISH
            else SwingType.LOW
        ),
        confirmation_index=8,
    )


def _event(direction: TrendDirection) -> BOSEvent:
    return BOSEvent(
        timestamp=NOW - timedelta(minutes=5),
        break_type=BreakType.BOS,
        direction=direction,
        swing_point=_swing(direction),
        break_price=2401.0,
        confirmation_index=10,
    )


def _sweep(direction: TrendDirection) -> LiquiditySweepEvent:
    is_buy_side = direction is TrendDirection.BEARISH
    level = LiquidityLevel(
        timestamp=NOW - timedelta(minutes=10),
        price=2410.0 if is_buy_side else 2390.0,
        swing_point=SwingPoint(
            timestamp=NOW - timedelta(minutes=15),
            index=6,
            price=2410.0 if is_buy_side else 2390.0,
            swing_type=SwingType.HIGH if is_buy_side else SwingType.LOW,
            confirmation_index=8,
        ),
        is_buy_side=is_buy_side,
    )
    return LiquiditySweepEvent(
        timestamp=NOW - timedelta(minutes=5),
        liquidity_level=level,
        sweep_price=level.price,
        confirmation_index=10,
    )


def _opposing(direction: TrendDirection) -> LiquidityLevel:
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


def _gap(direction: TrendDirection) -> FairValueGapCandidate:
    return FairValueGapCandidate(
        timestamp=NOW - timedelta(minutes=5),
        gap_type=(
            FairValueGapType.BULLISH
            if direction is TrendDirection.BULLISH
            else FairValueGapType.BEARISH
        ),
        top_price=2405.0,
        bottom_price=2402.0,
        first_bar=_bar(-15),
        middle_bar=_bar(-10),
        third_bar=_bar(-5),
    )


def _structure(
    direction: TrendDirection,
    event: BOSEvent | None,
    sweep: LiquiditySweepEvent | None,
    opposing: LiquidityLevel | None,
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
        tracked_liquidity_levels=(opposing,) if opposing is not None else (),
    )


def _context(
    direction: TrendDirection = TrendDirection.BULLISH,
    *,
    bias: MarketBias | None = None,
    event: BOSEvent | None | object = ...,
    sweep: LiquiditySweepEvent | None | object = ...,
    gap: FairValueGapCandidate | None | object = ...,
    price_location: PriceLocation = PriceLocation.UNKNOWN,
    displacement_present: bool | None = None,
    session_name: str | None = None,
    regime_name: str | None = None,
    missing_capabilities: tuple[str, ...] = (
        "dealing_range_price_location",
        "displacement_detection",
        "session_context",
        "market_regime",
    ),
) -> SMCICTContext:
    actual_event = _event(direction) if event is ... else event
    actual_sweep = _sweep(direction) if sweep is ... else sweep
    actual_gap = _gap(direction) if gap is ... else gap
    actual_bias = bias or (
        MarketBias.BULLISH
        if direction is TrendDirection.BULLISH
        else MarketBias.BEARISH
    )
    opposing = _opposing(direction)
    structure = _structure(direction, actual_event, actual_sweep, opposing)

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
        opposing_liquidity_level=opposing,
        active_fair_value_gap=actual_gap,
        active_order_block=None,
        latest_structure_event_timeframe=(
            Timeframe.M15 if actual_event is not None else None
        ),
        latest_liquidity_sweep_timeframe=(
            Timeframe.M15 if actual_sweep is not None else None
        ),
        opposing_liquidity_timeframe=Timeframe.M15,
        active_fair_value_gap_timeframe=(
            Timeframe.M15 if actual_gap is not None else None
        ),
        active_order_block_timeframe=None,
        price_location=price_location,
        displacement_present=displacement_present,
        session_name=session_name,
        regime_name=regime_name,
        missing_capabilities=missing_capabilities,
    )


def _codes(conditions) -> set[str]:
    return {condition.code for condition in conditions}


def test_returns_incomplete_when_required_ict_capabilities_are_unavailable() -> None:
    result = ICTMethodologyEvaluator().evaluate(_context())

    assert result.methodology is MethodologyIdentifier.ICT
    assert result.evaluation_status is MethodologyEvaluationStatus.INCOMPLETE
    assert result.direction is MethodologyDirection.BULLISH
    assert result.confidence is None
    assert {
        "PRICE_LOCATION_ALIGNED",
        "DISPLACEMENT_PRESENT",
        "SESSION_CONTEXT_PRESENT",
    }.issubset(_codes(result.unavailable_conditions))


def test_confirms_bullish_ict_when_all_required_facts_are_available() -> None:
    result = ICTMethodologyEvaluator().evaluate(
        _context(
            price_location=PriceLocation.DISCOUNT,
            displacement_present=True,
            session_name="London",
            regime_name="trending",
            missing_capabilities=(),
        )
    )

    assert result.evaluation_status is MethodologyEvaluationStatus.CONFIRMED
    assert result.direction is MethodologyDirection.BULLISH
    assert result.reason_codes == ("ICT_CONFIRMED",)


def test_confirms_bearish_ict_when_all_required_facts_are_available() -> None:
    result = ICTMethodologyEvaluator().evaluate(
        _context(
            TrendDirection.BEARISH,
            price_location=PriceLocation.PREMIUM,
            displacement_present=True,
            session_name="New York",
            missing_capabilities=(),
        )
    )

    assert result.evaluation_status is MethodologyEvaluationStatus.CONFIRMED
    assert result.direction is MethodologyDirection.BEARISH


def test_neutral_bias_is_not_confirmed() -> None:
    result = ICTMethodologyEvaluator().evaluate(
        _context(bias=MarketBias.NEUTRAL)
    )

    assert result.evaluation_status is MethodologyEvaluationStatus.NOT_CONFIRMED
    assert "HTF_BIAS_ALIGNED" in _codes(result.failed_conditions)


def test_missing_structure_shift_fails_presence_and_marks_alignment_unavailable() -> None:
    result = ICTMethodologyEvaluator().evaluate(_context(event=None))

    assert result.evaluation_status is MethodologyEvaluationStatus.NOT_CONFIRMED
    assert "STRUCTURE_SHIFT_PRESENT" in _codes(result.failed_conditions)
    assert "STRUCTURE_SHIFT_ALIGNED" in _codes(
        result.unavailable_conditions
    )


def test_structure_shift_conflict_fails_alignment() -> None:
    result = ICTMethodologyEvaluator().evaluate(
        _context(event=_event(TrendDirection.BEARISH))
    )

    assert result.evaluation_status is MethodologyEvaluationStatus.NOT_CONFIRMED
    assert "STRUCTURE_SHIFT_ALIGNED" in _codes(result.failed_conditions)


def test_missing_sweep_fails_presence() -> None:
    result = ICTMethodologyEvaluator().evaluate(_context(sweep=None))

    assert result.evaluation_status is MethodologyEvaluationStatus.NOT_CONFIRMED
    assert "LIQUIDITY_SWEEP_PRESENT" in _codes(result.failed_conditions)
    assert "LIQUIDITY_SWEEP_COMPATIBLE" in _codes(
        result.unavailable_conditions
    )


def test_incompatible_sweep_side_fails() -> None:
    result = ICTMethodologyEvaluator().evaluate(
        _context(sweep=_sweep(TrendDirection.BEARISH))
    )

    assert result.evaluation_status is MethodologyEvaluationStatus.NOT_CONFIRMED
    assert "LIQUIDITY_SWEEP_COMPATIBLE" in _codes(
        result.failed_conditions
    )


def test_missing_fvg_fails_required_rule() -> None:
    result = ICTMethodologyEvaluator().evaluate(_context(gap=None))

    assert result.evaluation_status is MethodologyEvaluationStatus.NOT_CONFIRMED
    assert "FAIR_VALUE_GAP_PRESENT" in _codes(result.failed_conditions)
    assert "FAIR_VALUE_GAP_ALIGNED" in _codes(
        result.unavailable_conditions
    )


def test_wrong_direction_fvg_fails_alignment() -> None:
    result = ICTMethodologyEvaluator().evaluate(
        _context(gap=_gap(TrendDirection.BEARISH))
    )

    assert result.evaluation_status is MethodologyEvaluationStatus.NOT_CONFIRMED
    assert "FAIR_VALUE_GAP_ALIGNED" in _codes(result.failed_conditions)


def test_known_wrong_price_location_fails_not_unavailable() -> None:
    result = ICTMethodologyEvaluator().evaluate(
        _context(
            price_location=PriceLocation.PREMIUM,
            displacement_present=True,
            session_name="London",
            missing_capabilities=(),
        )
    )

    assert result.evaluation_status is MethodologyEvaluationStatus.NOT_CONFIRMED
    assert "PRICE_LOCATION_ALIGNED" in _codes(result.failed_conditions)
    assert "PRICE_LOCATION_ALIGNED" not in _codes(
        result.unavailable_conditions
    )


def test_known_absent_displacement_fails_not_unavailable() -> None:
    result = ICTMethodologyEvaluator().evaluate(
        _context(
            price_location=PriceLocation.DISCOUNT,
            displacement_present=False,
            session_name="London",
            missing_capabilities=(),
        )
    )

    assert result.evaluation_status is MethodologyEvaluationStatus.NOT_CONFIRMED
    assert "DISPLACEMENT_PRESENT" in _codes(result.failed_conditions)


def test_regime_is_optional_and_does_not_block_confirmation() -> None:
    result = ICTMethodologyEvaluator().evaluate(
        _context(
            price_location=PriceLocation.DISCOUNT,
            displacement_present=True,
            session_name="London",
            regime_name=None,
            missing_capabilities=("market_regime",),
        )
    )

    assert result.evaluation_status is MethodologyEvaluationStatus.CONFIRMED
    regime = next(
        condition
        for condition in result.unavailable_conditions
        if condition.code == "MARKET_REGIME_PRESENT"
    )
    assert regime.required is False


def test_identical_context_produces_identical_result() -> None:
    context = _context()
    evaluator = ICTMethodologyEvaluator()

    assert evaluator.evaluate(context) == evaluator.evaluate(context)


def test_wrong_input_type_is_rejected() -> None:
    with pytest.raises(TypeError, match="context must be SMCICTContext"):
        ICTMethodologyEvaluator().evaluate(object())


def test_result_is_observational_only() -> None:
    result = ICTMethodologyEvaluator().evaluate(_context())

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
    import core.strategies.ict_methodology as module

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
