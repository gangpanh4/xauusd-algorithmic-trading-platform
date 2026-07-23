from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.data.models import MarketBar
from core.market_structure.enums import (
    BreakType,
    MarketTrend,
    SwingType,
    TrendDirection,
)
from core.market_structure.measurements import MarketStructureMeasurements
from core.market_structure.models import (
    BOSEvent,
    MarketStructureResult,
    StructureState,
    SwingPoint,
)
from core.multi_timeframe.enums import (
    MarketBias,
    Timeframe,
    TimeframeAlignment,
)
from core.multi_timeframe.models import (
    MultiTimeframeResult,
    TimeframeState,
)
from core.strategies import (
    SetupDirection,
    SetupStatus,
    StrategyContext,
    XAUUSDBOSCHOCHStrategy,
)


def _swing(index: int, price: float, kind: SwingType) -> SwingPoint:
    return SwingPoint(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC)
        + timedelta(minutes=5 * index),
        index=index,
        price=price,
        swing_type=kind,
        confirmation_index=index,
    )


def _event(
    index: int,
    direction: TrendDirection,
    swing: SwingPoint,
) -> BOSEvent:
    return BOSEvent(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC)
        + timedelta(minutes=5 * index),
        break_type=BreakType.BOS,
        direction=direction,
        swing_point=swing,
        break_price=swing.price + (
            1.0 if direction is TrendDirection.BULLISH else -1.0
        ),
        confirmation_index=index,
        age=0,
    )


def _structure_result(state: StructureState) -> MarketStructureResult:
    return MarketStructureResult(
        timestamp=state.timestamp,
        last_swing=state.last_swing,
        last_bos=state.last_bos,
        last_choch=state.last_choch,
        last_liquidity=state.last_liquidity,
        current_trend=state.trend,
        structure_confidence=1.0,
        measurements=MarketStructureMeasurements(),
        structure_state=state,
    )


def _tf(
    timeframe: Timeframe,
    bias: MarketBias,
    state: StructureState,
) -> TimeframeState:
    return TimeframeState(
        timeframe=timeframe,
        timestamp=state.timestamp,
        bias=bias,
        alignment=TimeframeAlignment.ALIGNED,
        confidence=1.0,
        market_structure=_structure_result(state),
    )


def _context(
    *,
    index: int,
    h4_bias: MarketBias = MarketBias.BULLISH,
    h1_bias: MarketBias = MarketBias.BULLISH,
    m5_trigger: bool = False,
    close: float = 3300.0,
) -> StrategyContext:
    timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=UTC) + timedelta(
        minutes=5 * index
    )
    m15_low = _swing(10, 3280.0, SwingType.LOW)
    m15_high = _swing(11, 3295.0, SwingType.HIGH)
    m15_event = _event(12, TrendDirection.BULLISH, m15_high)
    m15_state = StructureState(
        timestamp=timestamp,
        current_bar_index=index,
        trend=MarketTrend.BULLISH,
        confirmed_swings=(m15_low, m15_high),
        last_swing=m15_high,
        last_high=m15_high,
        last_low=m15_low,
        protected_low=m15_low,
        last_bos=m15_event,
    )

    h1_low = _swing(5, 3250.0, SwingType.LOW)
    h1_high = _swing(6, 3340.0, SwingType.HIGH)
    h1_state = StructureState(
        timestamp=timestamp,
        current_bar_index=index,
        trend=MarketTrend.BULLISH,
        confirmed_swings=(h1_low, h1_high),
        last_swing=h1_high,
        last_high=h1_high,
        last_low=h1_low,
    )

    h4_state = StructureState(
        timestamp=timestamp,
        current_bar_index=index,
        trend=MarketTrend.BULLISH,
    )

    m5_low = _swing(index - 1, 3290.0, SwingType.LOW)
    m5_high = _swing(index, 3299.0, SwingType.HIGH)
    m5_event = (
        _event(index, TrendDirection.BULLISH, m5_high)
        if m5_trigger
        else None
    )
    m5_state = StructureState(
        timestamp=timestamp,
        current_bar_index=index,
        trend=MarketTrend.BULLISH,
        confirmed_swings=(m5_low, m5_high),
        last_swing=m5_high,
        last_high=m5_high,
        last_low=m5_low,
        last_bos=m5_event,
    )

    neutral = StructureState(
        timestamp=timestamp,
        current_bar_index=index,
        trend=MarketTrend.UNKNOWN,
    )
    result = MultiTimeframeResult(
        weekly=_tf(Timeframe.WEEKLY, MarketBias.NEUTRAL, neutral),
        daily=_tf(Timeframe.DAILY, MarketBias.NEUTRAL, neutral),
        h4=_tf(Timeframe.H4, h4_bias, h4_state),
        h1=_tf(Timeframe.H1, h1_bias, h1_state),
        m15=_tf(Timeframe.M15, MarketBias.BULLISH, m15_state),
        m5=_tf(Timeframe.M5, MarketBias.BULLISH, m5_state),
        timestamp=timestamp,
    )
    bar = MarketBar(
        timestamp=timestamp,
        open=close - 1.0,
        high=close + 1.0,
        low=close - 2.0,
        close=close,
        tick_volume=100,
    )
    return StrategyContext(
        multi_timeframe=result,
        current_bar=bar,
        current_bar_index=index,
    )


def test_no_setup_when_h4_h1_bias_conflicts() -> None:
    strategy = XAUUSDBOSCHOCHStrategy()
    observation = strategy.observe(
        _context(
            index=20,
            h4_bias=MarketBias.BULLISH,
            h1_bias=MarketBias.BEARISH,
        )
    )
    assert observation.reason_code == "NO_SETUP"
    assert observation.setup is None


def test_detects_active_buy_setup_from_aligned_htf_and_m15_bos() -> None:
    strategy = XAUUSDBOSCHOCHStrategy()
    observation = strategy.observe(_context(index=20))

    assert observation.reason_code == "SETUP_DETECTED"
    assert observation.setup is not None
    assert observation.setup.status is SetupStatus.ACTIVE
    assert observation.setup.direction is SetupDirection.BUY
    assert observation.setup.invalidation.price == 3280.0
    assert observation.setup.target_references[0].price == 3340.0


def test_setup_requires_later_fresh_m5_trigger() -> None:
    strategy = XAUUSDBOSCHOCHStrategy()
    detected = strategy.observe(_context(index=20))
    assert detected.setup is not None

    waiting = strategy.observe(_context(index=21, m5_trigger=False))
    assert waiting.reason_code == "SETUP_ACTIVE"
    assert waiting.candidate_trade is None

    triggered = strategy.observe(_context(index=22, m5_trigger=True))
    assert triggered.reason_code == "CANDIDATE_CREATED"
    assert triggered.trigger is not None
    assert triggered.candidate_trade is not None
    assert triggered.setup is not None
    assert triggered.setup.status is SetupStatus.CONSUMED
    assert triggered.candidate_trade.metadata["observational_only"] is True


def test_setup_invalidates_when_price_crosses_structural_level() -> None:
    strategy = XAUUSDBOSCHOCHStrategy()
    strategy.observe(_context(index=20))

    invalidated = strategy.observe(
        _context(index=21, close=3279.0)
    )
    assert invalidated.reason_code == SetupStatus.INVALIDATED.value
    assert invalidated.setup is not None
    assert invalidated.setup.status is SetupStatus.INVALIDATED
    assert invalidated.candidate_trade is None
