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
    CHOCHEvent,
    LiquidityLevel,
    LiquiditySweepEvent,
    StructureState,
    SwingPoint,
)
from core.multi_timeframe.enums import MarketBias, Timeframe
from core.multi_timeframe.models import MultiTimeframeResult, TimeframeState
from core.order_block_detector.models import OrderBlock
from core.price_action.models import PriceActionResult
from core.strategies.context import StrategyContext
from core.strategies.smc_ict_context import PriceLocation
from core.strategies.smc_ict_context_builder import SMCICTContextBuilder


NOW = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)


def _bar(minutes: int, close: float = 2401.0) -> MarketBar:
    timestamp = NOW + timedelta(minutes=minutes)
    return MarketBar(
        timestamp=timestamp,
        open=close - 1.0,
        high=close + 1.0,
        low=close - 2.0,
        close=close,
        tick_volume=1,
    )


def _swing(
    *,
    minutes: int,
    index: int,
    confirmation_index: int,
    price: float,
    swing_type: SwingType,
) -> SwingPoint:
    return SwingPoint(
        timestamp=NOW + timedelta(minutes=minutes),
        index=index,
        price=price,
        swing_type=swing_type,
        confirmation_index=confirmation_index,
    )


def _event(
    *,
    minutes: int,
    confirmation_index: int,
    direction: TrendDirection,
    choch: bool = False,
    swing: SwingPoint | None = None,
):
    swing = swing or _swing(
        minutes=minutes - 5,
        index=max(0, confirmation_index - 2),
        confirmation_index=max(0, confirmation_index - 1),
        price=2390.0 if direction is TrendDirection.BULLISH else 2410.0,
        swing_type=(
            SwingType.HIGH
            if direction is TrendDirection.BULLISH
            else SwingType.LOW
        ),
    )
    event_type = CHOCHEvent if choch else BOSEvent
    return event_type(
        timestamp=NOW + timedelta(minutes=minutes),
        break_type=BreakType.CHOCH if choch else BreakType.BOS,
        direction=direction,
        swing_point=swing,
        break_price=2402.0,
        confirmation_index=confirmation_index,
    )


def _level(
    *,
    minutes: int,
    price: float,
    is_buy_side: bool,
    confirmation_index: int = 8,
) -> LiquidityLevel:
    return LiquidityLevel(
        timestamp=NOW + timedelta(minutes=minutes),
        price=price,
        swing_point=_swing(
            minutes=minutes - 5,
            index=max(0, confirmation_index - 2),
            confirmation_index=confirmation_index,
            price=price,
            swing_type=SwingType.HIGH if is_buy_side else SwingType.LOW,
        ),
        is_buy_side=is_buy_side,
    )


def _sweep(
    *,
    minutes: int,
    confirmation_index: int,
    level: LiquidityLevel,
) -> LiquiditySweepEvent:
    return LiquiditySweepEvent(
        timestamp=NOW + timedelta(minutes=minutes),
        liquidity_level=level,
        sweep_price=level.price,
        confirmation_index=confirmation_index,
    )


def _structure(
    *,
    minutes: int = 0,
    current_bar_index: int = 20,
    bos: BOSEvent | None = None,
    choch: CHOCHEvent | None = None,
    sweep: LiquiditySweepEvent | None = None,
    levels: tuple[LiquidityLevel, ...] = (),
) -> StructureState:
    return StructureState(
        timestamp=NOW + timedelta(minutes=minutes),
        current_bar_index=current_bar_index,
        trend=MarketTrend.BULLISH,
        last_bos=bos,
        last_choch=choch,
        last_liquidity=sweep,
        tracked_liquidity_levels=levels,
    )


def _state(
    timeframe: Timeframe,
    bias: MarketBias,
    *,
    structure: StructureState | None = None,
    price_action: PriceActionResult | None = None,
    minutes: int = 0,
) -> TimeframeState:
    return TimeframeState(
        timeframe=timeframe,
        timestamp=NOW + timedelta(minutes=minutes),
        bias=bias,
        market_structure=structure,
        price_action=price_action,
    )


def _context(
    h4: MarketBias = MarketBias.NEUTRAL,
    h1: MarketBias = MarketBias.NEUTRAL,
    *,
    h4_state: TimeframeState | None = None,
    h1_state: TimeframeState | None = None,
    m15_state: TimeframeState | None = None,
    m5_state: TimeframeState | None = None,
) -> StrategyContext:
    result = MultiTimeframeResult(
        weekly=_state(Timeframe.WEEKLY, MarketBias.NEUTRAL),
        daily=_state(Timeframe.DAILY, MarketBias.NEUTRAL),
        h4=h4_state or _state(Timeframe.H4, h4),
        h1=h1_state or _state(Timeframe.H1, h1),
        m15=m15_state or _state(Timeframe.M15, MarketBias.NEUTRAL),
        m5=m5_state or _state(Timeframe.M5, MarketBias.NEUTRAL),
        timestamp=NOW,
    )
    return StrategyContext(
        multi_timeframe=result,
        current_bar=_bar(0),
        current_bar_index=20,
    )


def _price_action(
    *,
    minutes: int = 0,
    gap: FairValueGapCandidate | None = None,
    block: OrderBlock | None = None,
) -> PriceActionResult:
    return PriceActionResult(
        timestamp=NOW + timedelta(minutes=minutes),
        last_order_block=block,
        last_fair_value_gap=gap,
        price_action_confidence=0.0,
    )


def _gap(
    *,
    minutes: int,
    third_bar_minutes: int | None = None,
) -> FairValueGapCandidate:
    third = minutes if third_bar_minutes is None else third_bar_minutes
    return FairValueGapCandidate(
        timestamp=NOW + timedelta(minutes=minutes),
        gap_type=FairValueGapType.BULLISH,
        top_price=2405.0,
        bottom_price=2402.0,
        first_bar=_bar(third - 10),
        middle_bar=_bar(third - 5),
        third_bar=_bar(third),
    )


def _order_block(
    *,
    minutes: int,
    confirmation_index: int,
    direction: TrendDirection = TrendDirection.BULLISH,
) -> OrderBlock:
    swing = _swing(
        minutes=minutes - 10,
        index=max(0, confirmation_index - 3),
        confirmation_index=max(0, confirmation_index - 2),
        price=2395.0,
        swing_type=SwingType.LOW,
    )
    trigger = _event(
        minutes=minutes - 5,
        confirmation_index=max(0, confirmation_index - 1),
        direction=direction,
        swing=swing,
    )
    return OrderBlock(
        timestamp=NOW + timedelta(minutes=minutes),
        block_type=(
            OrderBlockType.BULLISH
            if direction is TrendDirection.BULLISH
            else OrderBlockType.BEARISH
        ),
        top_price=2400.0,
        bottom_price=2395.0,
        origin_swing=swing,
        trigger_break=trigger,
        trigger_liquidity=None,
        creation_index=max(0, confirmation_index - 2),
        confirmation_index=confirmation_index,
    )


def test_builder_preserves_aligned_htf_bias_and_unknown_capabilities() -> None:
    result = SMCICTContextBuilder().build(
        _context(MarketBias.BULLISH, MarketBias.BULLISH)
    )

    assert result.higher_timeframe_bias is MarketBias.BULLISH
    assert result.current_price == 2401.0
    assert result.price_location is PriceLocation.UNKNOWN
    assert result.displacement_present is None
    assert result.session_name is None
    assert result.regime_name is None
    assert result.missing_capabilities == (
        "dealing_range_price_location",
        "displacement_detection",
        "session_context",
        "market_regime",
    )


def test_builder_returns_neutral_for_conflicting_bias() -> None:
    result = SMCICTContextBuilder().build(
        _context(MarketBias.BULLISH, MarketBias.BEARISH)
    )
    assert result.higher_timeframe_bias is MarketBias.NEUTRAL


def test_builder_rejects_wrong_type() -> None:
    with pytest.raises(TypeError, match="context must be StrategyContext"):
        SMCICTContextBuilder().build(object())


def test_latest_structure_event_uses_timestamp_not_cross_timeframe_index() -> None:
    older_m5 = _event(
        minutes=-20,
        confirmation_index=500,
        direction=TrendDirection.BULLISH,
    )
    newer_h4 = _event(
        minutes=-5,
        confirmation_index=10,
        direction=TrendDirection.BEARISH,
    )
    result = SMCICTContextBuilder().build(
        _context(
            m5_state=_state(
                Timeframe.M5,
                MarketBias.BULLISH,
                structure=_structure(bos=older_m5, current_bar_index=500),
            ),
            h4_state=_state(
                Timeframe.H4,
                MarketBias.BEARISH,
                structure=_structure(bos=newer_h4, current_bar_index=10),
            ),
        )
    )

    assert result.latest_structure_event is newer_h4
    assert result.latest_structure_event_timeframe is Timeframe.H4


def test_equal_event_timestamps_use_documented_m5_bos_priority() -> None:
    m5_bos = _event(
        minutes=-5,
        confirmation_index=10,
        direction=TrendDirection.BULLISH,
    )
    m15_choch = _event(
        minutes=-5,
        confirmation_index=10,
        direction=TrendDirection.BEARISH,
        choch=True,
    )
    result = SMCICTContextBuilder().build(
        _context(
            m5_state=_state(
                Timeframe.M5,
                MarketBias.BULLISH,
                structure=_structure(bos=m5_bos),
            ),
            m15_state=_state(
                Timeframe.M15,
                MarketBias.BEARISH,
                structure=_structure(choch=m15_choch),
            ),
        )
    )

    assert result.latest_structure_event is m5_bos
    assert result.latest_structure_event_timeframe is Timeframe.M5


@pytest.mark.parametrize(
    "event",
    [
        _event(
            minutes=5,
            confirmation_index=10,
            direction=TrendDirection.BULLISH,
        ),
        _event(
            minutes=5,
            confirmation_index=10,
            direction=TrendDirection.BEARISH,
            choch=True,
        ),
    ],
)
def test_future_structure_events_are_rejected(event) -> None:
    structure = _structure(
        bos=event if isinstance(event, BOSEvent) else None,
        choch=event if isinstance(event, CHOCHEvent) else None,
    )
    result = SMCICTContextBuilder().build(
        _context(
            m5_state=_state(
                Timeframe.M5,
                MarketBias.BULLISH,
                structure=structure,
            )
        )
    )

    assert result.latest_structure_event is None
    assert result.latest_structure_event_timeframe is None


def test_event_confirmation_after_source_structure_is_rejected() -> None:
    event = _event(
        minutes=-5,
        confirmation_index=21,
        direction=TrendDirection.BULLISH,
    )
    result = SMCICTContextBuilder().build(
        _context(
            m5_state=_state(
                Timeframe.M5,
                MarketBias.BULLISH,
                structure=_structure(
                    bos=event,
                    current_bar_index=20,
                ),
            )
        )
    )

    assert result.latest_structure_event is None


def test_latest_sweep_uses_timestamp_and_records_source_timeframe() -> None:
    m5_level = _level(minutes=-30, price=2410.0, is_buy_side=True)
    h1_level = _level(minutes=-15, price=2415.0, is_buy_side=True)
    older_m5 = _sweep(
        minutes=-20,
        confirmation_index=300,
        level=m5_level,
    )
    newer_h1 = _sweep(
        minutes=-5,
        confirmation_index=10,
        level=h1_level,
    )
    result = SMCICTContextBuilder().build(
        _context(
            m5_state=_state(
                Timeframe.M5,
                MarketBias.BULLISH,
                structure=_structure(
                    sweep=older_m5,
                    current_bar_index=300,
                ),
            ),
            h1_state=_state(
                Timeframe.H1,
                MarketBias.BULLISH,
                structure=_structure(
                    sweep=newer_h1,
                    current_bar_index=10,
                ),
            ),
        )
    )

    assert result.latest_liquidity_sweep is newer_h1
    assert result.latest_liquidity_sweep_timeframe is Timeframe.H1


def test_future_sweep_is_rejected() -> None:
    level = _level(minutes=-5, price=2410.0, is_buy_side=True)
    sweep = _sweep(minutes=5, confirmation_index=10, level=level)
    result = SMCICTContextBuilder().build(
        _context(
            m5_state=_state(
                Timeframe.M5,
                MarketBias.BULLISH,
                structure=_structure(sweep=sweep),
            )
        )
    )

    assert result.latest_liquidity_sweep is None
    assert result.latest_liquidity_sweep_timeframe is None


def test_bullish_event_selects_nearest_buy_side_liquidity_from_same_timeframe() -> None:
    event = _event(
        minutes=-5,
        confirmation_index=10,
        direction=TrendDirection.BULLISH,
    )
    far = _level(minutes=-10, price=2420.0, is_buy_side=True)
    near = _level(minutes=-10, price=2410.0, is_buy_side=True)
    wrong_side = _level(minutes=-10, price=2390.0, is_buy_side=False)
    result = SMCICTContextBuilder().build(
        _context(
            m15_state=_state(
                Timeframe.M15,
                MarketBias.BULLISH,
                structure=_structure(
                    bos=event,
                    levels=(far, near, wrong_side),
                ),
            )
        )
    )

    assert result.opposing_liquidity_level is near
    assert result.opposing_liquidity_timeframe is Timeframe.M15


def test_bearish_event_selects_nearest_sell_side_liquidity_below_price() -> None:
    event = _event(
        minutes=-5,
        confirmation_index=10,
        direction=TrendDirection.BEARISH,
    )
    far = _level(minutes=-10, price=2380.0, is_buy_side=False)
    near = _level(minutes=-10, price=2395.0, is_buy_side=False)
    wrong_side = _level(minutes=-10, price=2420.0, is_buy_side=True)
    result = SMCICTContextBuilder().build(
        _context(
            m15_state=_state(
                Timeframe.M15,
                MarketBias.BEARISH,
                structure=_structure(
                    bos=event,
                    levels=(far, near, wrong_side),
                ),
            )
        )
    )

    assert result.opposing_liquidity_level is near
    assert result.opposing_liquidity_timeframe is Timeframe.M15


def test_m5_fvg_is_used_when_m15_has_no_fvg() -> None:
    gap = _gap(minutes=-5)
    result = SMCICTContextBuilder().build(
        _context(
            m15_state=_state(
                Timeframe.M15,
                MarketBias.NEUTRAL,
                price_action=_price_action(),
            ),
            m5_state=_state(
                Timeframe.M5,
                MarketBias.NEUTRAL,
                price_action=_price_action(gap=gap),
            ),
        )
    )

    assert result.active_fair_value_gap is gap
    assert result.active_fair_value_gap_timeframe is Timeframe.M5


def test_newest_fvg_is_selected_by_timestamp() -> None:
    older_m15 = _gap(minutes=-15)
    newer_m5 = _gap(minutes=-5)
    result = SMCICTContextBuilder().build(
        _context(
            m15_state=_state(
                Timeframe.M15,
                MarketBias.NEUTRAL,
                price_action=_price_action(minutes=-15, gap=older_m15),
            ),
            m5_state=_state(
                Timeframe.M5,
                MarketBias.NEUTRAL,
                price_action=_price_action(minutes=-5, gap=newer_m5),
            ),
        )
    )

    assert result.active_fair_value_gap is newer_m5
    assert result.active_fair_value_gap_timeframe is Timeframe.M5


def test_fvg_with_future_third_bar_is_rejected() -> None:
    gap = _gap(minutes=-5, third_bar_minutes=5)
    result = SMCICTContextBuilder().build(
        _context(
            m5_state=_state(
                Timeframe.M5,
                MarketBias.NEUTRAL,
                price_action=_price_action(gap=gap),
            )
        )
    )

    assert result.active_fair_value_gap is None
    assert result.active_fair_value_gap_timeframe is None


def test_m5_order_block_is_used_when_m15_has_no_order_block() -> None:
    block = _order_block(minutes=-5, confirmation_index=10)
    structure = _structure(current_bar_index=20)
    result = SMCICTContextBuilder().build(
        _context(
            m15_state=_state(
                Timeframe.M15,
                MarketBias.NEUTRAL,
                structure=structure,
                price_action=_price_action(),
            ),
            m5_state=_state(
                Timeframe.M5,
                MarketBias.NEUTRAL,
                structure=structure,
                price_action=_price_action(block=block),
            ),
        )
    )

    assert result.active_order_block is block
    assert result.active_order_block_timeframe is Timeframe.M5


def test_future_order_block_is_rejected() -> None:
    block = _order_block(minutes=5, confirmation_index=10)
    result = SMCICTContextBuilder().build(
        _context(
            m5_state=_state(
                Timeframe.M5,
                MarketBias.NEUTRAL,
                structure=_structure(current_bar_index=20),
                price_action=_price_action(block=block),
            )
        )
    )

    assert result.active_order_block is None
    assert result.active_order_block_timeframe is None


def test_order_block_confirmation_after_source_structure_is_rejected() -> None:
    block = _order_block(minutes=-5, confirmation_index=21)
    result = SMCICTContextBuilder().build(
        _context(
            m5_state=_state(
                Timeframe.M5,
                MarketBias.NEUTRAL,
                structure=_structure(current_bar_index=20),
                price_action=_price_action(block=block),
            )
        )
    )

    assert result.active_order_block is None


def test_future_structure_snapshot_is_not_published() -> None:
    future = _structure(minutes=5)
    result = SMCICTContextBuilder().build(
        _context(
            h4_state=_state(
                Timeframe.H4,
                MarketBias.BULLISH,
                structure=future,
                minutes=5,
            )
        )
    )

    assert result.h4_structure is None


def test_provenance_is_none_when_fact_is_absent() -> None:
    result = SMCICTContextBuilder().build(_context())

    assert result.latest_structure_event_timeframe is None
    assert result.latest_liquidity_sweep_timeframe is None
    assert result.opposing_liquidity_timeframe is None
    assert result.active_fair_value_gap_timeframe is None
    assert result.active_order_block_timeframe is None


def test_builder_classifies_discount_from_confirmed_h1_dealing_range() -> None:
    high = _swing(
        minutes=-20,
        index=5,
        confirmation_index=8,
        price=2420.0,
        swing_type=SwingType.HIGH,
    )
    low = _swing(
        minutes=-30,
        index=3,
        confirmation_index=7,
        price=2380.0,
        swing_type=SwingType.LOW,
    )
    structure = replace(
        _structure(current_bar_index=20),
        last_high=high,
        last_low=low,
    )
    context = _context(
        h1_state=_state(
            Timeframe.H1,
            MarketBias.BULLISH,
            structure=structure,
        )
    )
    context = replace(
        context,
        current_bar=MarketBar(
            timestamp=NOW,
            open=2389.0,
            high=2392.0,
            low=2388.0,
            close=2390.0,
            tick_volume=1,
        ),
    )

    result = SMCICTContextBuilder().build(context)

    assert result.dealing_range_high == 2420.0
    assert result.dealing_range_low == 2380.0
    assert result.dealing_range_equilibrium == 2400.0
    assert result.dealing_range_timeframe is Timeframe.H1
    assert result.price_location is PriceLocation.DISCOUNT
    assert "dealing_range_price_location" not in result.missing_capabilities


def test_builder_classifies_premium_from_confirmed_range() -> None:
    high = _swing(
        minutes=-20,
        index=5,
        confirmation_index=8,
        price=2420.0,
        swing_type=SwingType.HIGH,
    )
    low = _swing(
        minutes=-30,
        index=3,
        confirmation_index=7,
        price=2380.0,
        swing_type=SwingType.LOW,
    )
    structure = replace(
        _structure(current_bar_index=20),
        last_high=high,
        last_low=low,
    )
    context = _context(
        h1_state=_state(
            Timeframe.H1,
            MarketBias.BULLISH,
            structure=structure,
        )
    )
    context = replace(
        context,
        current_bar=MarketBar(
            timestamp=NOW,
            open=2410.0,
            high=2412.0,
            low=2408.0,
            close=2410.0,
            tick_volume=1,
        ),
    )

    result = SMCICTContextBuilder().build(context)

    assert result.price_location is PriceLocation.PREMIUM
    assert result.dealing_range_timeframe is Timeframe.H1


def test_builder_classifies_exact_midpoint_as_equilibrium() -> None:
    high = _swing(
        minutes=-20,
        index=5,
        confirmation_index=8,
        price=2420.0,
        swing_type=SwingType.HIGH,
    )
    low = _swing(
        minutes=-30,
        index=3,
        confirmation_index=7,
        price=2380.0,
        swing_type=SwingType.LOW,
    )
    structure = replace(
        _structure(current_bar_index=20),
        last_high=high,
        last_low=low,
    )
    result = SMCICTContextBuilder().build(
        _context(
            h1_state=_state(
                Timeframe.H1,
                MarketBias.BULLISH,
                structure=structure,
            )
        )
    )

    assert result.current_price == 2401.0
    assert result.price_location is PriceLocation.PREMIUM

    midpoint_context = _context(
        h1_state=_state(
            Timeframe.H1,
            MarketBias.BULLISH,
            structure=structure,
        )
    )
    midpoint_context = replace(
        midpoint_context,
        current_bar=MarketBar(
            timestamp=NOW,
            open=2400.0,
            high=2401.0,
            low=2399.0,
            close=2400.0,
            tick_volume=1,
        ),
    )
    midpoint_result = SMCICTContextBuilder().build(midpoint_context)
    assert midpoint_result.price_location is PriceLocation.EQUILIBRIUM


def test_builder_uses_h1_before_h4_for_dealing_range() -> None:
    h1 = replace(
        _structure(current_bar_index=20),
        last_high=_swing(
            minutes=-20,
            index=5,
            confirmation_index=8,
            price=2420.0,
            swing_type=SwingType.HIGH,
        ),
        last_low=_swing(
            minutes=-30,
            index=3,
            confirmation_index=7,
            price=2380.0,
            swing_type=SwingType.LOW,
        ),
    )
    h4 = replace(
        _structure(current_bar_index=20),
        last_high=_swing(
            minutes=-40,
            index=5,
            confirmation_index=8,
            price=2500.0,
            swing_type=SwingType.HIGH,
        ),
        last_low=_swing(
            minutes=-50,
            index=3,
            confirmation_index=7,
            price=2300.0,
            swing_type=SwingType.LOW,
        ),
    )

    result = SMCICTContextBuilder().build(
        _context(
            h1_state=_state(Timeframe.H1, MarketBias.BULLISH, structure=h1),
            h4_state=_state(Timeframe.H4, MarketBias.BULLISH, structure=h4),
        )
    )

    assert result.dealing_range_timeframe is Timeframe.H1
    assert result.dealing_range_high == 2420.0
    assert result.dealing_range_low == 2380.0


def test_builder_rejects_future_or_unconfirmed_dealing_range_swings() -> None:
    future_high = _swing(
        minutes=5,
        index=5,
        confirmation_index=8,
        price=2420.0,
        swing_type=SwingType.HIGH,
    )
    unconfirmed_low = _swing(
        minutes=-30,
        index=3,
        confirmation_index=21,
        price=2380.0,
        swing_type=SwingType.LOW,
    )
    structure = replace(
        _structure(current_bar_index=20),
        last_high=future_high,
        last_low=unconfirmed_low,
    )

    result = SMCICTContextBuilder().build(
        _context(
            h1_state=_state(
                Timeframe.H1,
                MarketBias.BULLISH,
                structure=structure,
            )
        )
    )

    assert result.price_location is PriceLocation.UNKNOWN
    assert result.dealing_range_high is None
    assert result.dealing_range_low is None
    assert result.dealing_range_equilibrium is None
    assert result.dealing_range_timeframe is None
    assert "dealing_range_price_location" in result.missing_capabilities


def test_builder_rejects_invalid_dealing_range_geometry() -> None:
    high = _swing(
        minutes=-20,
        index=5,
        confirmation_index=8,
        price=2380.0,
        swing_type=SwingType.HIGH,
    )
    low = _swing(
        minutes=-30,
        index=3,
        confirmation_index=7,
        price=2420.0,
        swing_type=SwingType.LOW,
    )
    structure = replace(
        _structure(current_bar_index=20),
        last_high=high,
        last_low=low,
    )

    result = SMCICTContextBuilder().build(
        _context(
            h1_state=_state(
                Timeframe.H1,
                MarketBias.BULLISH,
                structure=structure,
            )
        )
    )

    assert result.price_location is PriceLocation.UNKNOWN
    assert "dealing_range_price_location" in result.missing_capabilities
