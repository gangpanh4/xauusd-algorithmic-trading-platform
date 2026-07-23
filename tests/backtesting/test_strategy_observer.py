from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.backtesting.strategy_observer import BacktestStrategyObserver
from core.data.models import MarketBar
from core.market_structure.enums import MarketTrend
from core.market_structure.measurements import MarketStructureMeasurements
from core.market_structure.models import MarketStructureResult, StructureState
from core.multi_timeframe.enums import MarketBias, Timeframe
from core.multi_timeframe.models import MultiTimeframeResult, TimeframeState


def _state(timeframe: Timeframe, timestamp: datetime) -> TimeframeState:
    structure = StructureState(
        timestamp=timestamp,
        current_bar_index=0,
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


def _mtf(timestamp: datetime) -> MultiTimeframeResult:
    return MultiTimeframeResult(
        weekly=_state(Timeframe.WEEKLY, timestamp),
        daily=_state(Timeframe.DAILY, timestamp),
        h4=_state(Timeframe.H4, timestamp),
        h1=_state(Timeframe.H1, timestamp),
        m15=_state(Timeframe.M15, timestamp),
        m5=_state(Timeframe.M5, timestamp),
        timestamp=timestamp,
    )


def _bar(timestamp: datetime) -> MarketBar:
    return MarketBar(
        timestamp=timestamp,
        open=3300.0,
        high=3301.0,
        low=3299.0,
        close=3300.0,
        tick_volume=100,
    )


def test_observer_records_strategy_results_without_trade_authorization() -> None:
    observer = BacktestStrategyObserver()
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)

    observation = observer.observe(
        multi_timeframe=_mtf(timestamp),
        current_bar=_bar(timestamp),
        current_bar_index=10,
    )

    assert observation.reason_code == 'NO_SETUP'
    assert observation.candidate_trade is None
    assert observer.candidate_count == 0
    assert observer.observation_summary() == {'NO_SETUP': 1}
    assert observer.observations == (observation,)


def test_observer_rejects_duplicate_timestamp_and_index() -> None:
    observer = BacktestStrategyObserver()
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)

    observer.observe(
        multi_timeframe=_mtf(timestamp),
        current_bar=_bar(timestamp),
        current_bar_index=10,
    )

    with pytest.raises(ValueError, match='timestamps'):
        observer.observe(
            multi_timeframe=_mtf(timestamp),
            current_bar=_bar(timestamp),
            current_bar_index=11,
        )


def test_observer_reset_clears_history_and_chronology() -> None:
    observer = BacktestStrategyObserver()
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)

    observer.observe(
        multi_timeframe=_mtf(timestamp),
        current_bar=_bar(timestamp),
        current_bar_index=10,
    )
    observer.reset()

    assert observer.observations == ()
    assert observer.observation_summary() == {}

    later = timestamp + timedelta(minutes=5)
    observation = observer.observe(
        multi_timeframe=_mtf(later),
        current_bar=_bar(later),
        current_bar_index=1,
    )
    assert observation.reason_code == 'NO_SETUP'
