from __future__ import annotations

from datetime import UTC, datetime

from core.backtesting.engine import BacktestingEngine
from core.backtesting.strategy_observer import BacktestStrategyObserver
from core.data.models import MarketBar as SharedMarketBar
from core.market_structure.enums import MarketTrend
from core.market_structure.measurements import MarketStructureMeasurements
from core.market_structure.models import MarketStructureResult, StructureState
from core.multi_timeframe.enums import MarketBias, Timeframe
from core.multi_timeframe.models import MultiTimeframeResult, TimeframeState
from core.regime_detector.models import MarketBar


def _state(
    timeframe: Timeframe,
    timestamp: datetime,
    *,
    structure_index: int,
) -> TimeframeState:
    structure = StructureState(
        timestamp=timestamp,
        current_bar_index=structure_index,
        trend=MarketTrend.UNKNOWN,
    )
    result = MarketStructureResult(
        timestamp=timestamp,
        last_swing=None,
        last_bos=None,
        last_choch=None,
        last_liquidity=None,
        current_trend=MarketTrend.UNKNOWN,
        structure_confidence=0.0,
        measurements=MarketStructureMeasurements(),
        structure_state=structure,
    )
    return TimeframeState(
        timeframe=timeframe,
        timestamp=timestamp,
        bias=MarketBias.NEUTRAL,
        market_structure=result,
    )


def _mtf(timestamp: datetime, structure_index: int) -> MultiTimeframeResult:
    return MultiTimeframeResult(
        weekly=_state(Timeframe.WEEKLY, timestamp, structure_index=1),
        daily=_state(Timeframe.DAILY, timestamp, structure_index=1),
        h4=_state(Timeframe.H4, timestamp, structure_index=1),
        h1=_state(Timeframe.H1, timestamp, structure_index=1),
        m15=_state(Timeframe.M15, timestamp, structure_index=3),
        m5=_state(
            Timeframe.M5,
            timestamp,
            structure_index=structure_index,
        ),
        timestamp=timestamp,
    )


def _engine() -> BacktestingEngine:
    engine = object.__new__(BacktestingEngine)
    engine.strategy_observer = BacktestStrategyObserver()
    return engine


def _bar(timestamp: datetime) -> MarketBar:
    return MarketBar(
        timestamp=timestamp,
        open=3300.0,
        high=3301.0,
        low=3299.0,
        close=3300.0,
        volume=100,
        tick_volume=100,
    )


def test_engine_observes_strategy_with_authoritative_m5_index() -> None:
    engine = _engine()
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)

    observation = engine._observe_strategy(
        multi_timeframe=_mtf(timestamp, structure_index=37),
        observation_bar=_bar(timestamp),
    )

    assert observation is not None
    assert observation.reason_code == 'NO_SETUP'
    assert engine.strategy_observer._last_bar_index == 37
    assert engine.strategy_candidate_count == 0
    assert engine.strategy_observation_summary() == {'NO_SETUP': 1}
    assert engine.strategy_observations == (observation,)


def test_engine_strategy_observation_does_not_touch_trade_state() -> None:
    engine = _engine()
    engine.state = object()
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)

    engine._observe_strategy(
        multi_timeframe=_mtf(timestamp, structure_index=10),
        observation_bar=_bar(timestamp),
    )

    assert engine.state is not None
    assert engine.strategy_candidate_count == 0


def test_engine_skips_observer_when_structure_state_is_missing() -> None:
    engine = _engine()
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    mtf = _mtf(timestamp, structure_index=10)
    m5_result = mtf.m5.market_structure
    assert isinstance(m5_result, MarketStructureResult)
    mtf.m5.market_structure = MarketStructureResult(
        timestamp=timestamp,
        last_swing=None,
        last_bos=None,
        last_choch=None,
        last_liquidity=None,
        current_trend=MarketTrend.UNKNOWN,
        structure_confidence=0.0,
        measurements=MarketStructureMeasurements(),
        structure_state=None,
    )

    observation = engine._observe_strategy(
        multi_timeframe=mtf,
        observation_bar=_bar(timestamp),
    )

    assert observation is None
    assert engine.strategy_observations == ()
