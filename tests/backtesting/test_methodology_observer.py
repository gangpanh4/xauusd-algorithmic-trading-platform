from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from core.backtesting.methodology_observer import (
    BacktestMethodologyObserver,
    MethodologyObservation,
)
from core.data.models import MarketBar
from core.market_structure.enums import MarketTrend
from core.market_structure.measurements import MarketStructureMeasurements
from core.market_structure.models import MarketStructureResult, StructureState
from core.multi_timeframe.enums import MarketBias, Timeframe
from core.multi_timeframe.models import MultiTimeframeResult, TimeframeState
from core.regime_detector.models import MarketRegime, RegimeLabel
from core.strategies.context import StrategyContext
from core.strategies.methodology_models import (
    MethodologyEvaluationStatus,
    MethodologyIdentifier,
)


def _state(timeframe: Timeframe, timestamp: datetime) -> TimeframeState:
    structure = StructureState(
        timestamp=timestamp,
        current_bar_index=10,
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


def _context(
    timestamp: datetime,
    *,
    regime: MarketRegime | None = None,
    index: int = 10,
) -> StrategyContext:
    mtf = MultiTimeframeResult(
        weekly=_state(Timeframe.WEEKLY, timestamp),
        daily=_state(Timeframe.DAILY, timestamp),
        h4=_state(Timeframe.H4, timestamp),
        h1=_state(Timeframe.H1, timestamp),
        m15=_state(Timeframe.M15, timestamp),
        m5=_state(Timeframe.M5, timestamp),
        timestamp=timestamp,
    )
    bar = MarketBar(
        timestamp=timestamp,
        open=3300.0,
        high=3301.0,
        low=3299.0,
        close=3300.0,
        tick_volume=100,
    )
    return StrategyContext(
        multi_timeframe=mtf,
        current_bar=bar,
        current_bar_index=index,
        market_regime=regime,
    )


def _regime(timestamp: datetime) -> MarketRegime:
    return MarketRegime(
        primary_regime=RegimeLabel.TRENDING_BULL,
        confidence=0.80,
        observation_timestamp=timestamp,
        computation_timestamp=timestamp,
    )


def test_observer_builds_one_shared_context_and_both_results() -> None:
    timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    observer = BacktestMethodologyObserver()

    observation = observer.observe(
        _context(timestamp, regime=_regime(timestamp))
    )

    assert isinstance(observation, MethodologyObservation)
    assert observation.timestamp == timestamp
    assert observation.context.timestamp == timestamp
    assert observation.context.regime_name == "TRENDING_BULL"
    assert observation.smc.methodology is MethodologyIdentifier.SMC
    assert observation.ict.methodology is MethodologyIdentifier.ICT
    assert observation.smc.timestamp == timestamp
    assert observation.ict.timestamp == timestamp
    assert observer.observations == (observation,)


def test_results_remain_observational_without_trade_authority() -> None:
    timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    observation = BacktestMethodologyObserver().observe(_context(timestamp))

    prohibited = {
        "entry_price",
        "stop_loss",
        "target_price",
        "position_size",
        "signal",
        "trade_plan",
        "approved",
        "authorized",
        "execution_status",
    }
    assert prohibited.isdisjoint(type(observation.smc).__dataclass_fields__)
    assert prohibited.isdisjoint(type(observation.ict).__dataclass_fields__)


def test_observation_is_immutable() -> None:
    timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    observation = BacktestMethodologyObserver().observe(_context(timestamp))

    with pytest.raises(FrozenInstanceError):
        observation.timestamp = timestamp + timedelta(minutes=5)


def test_summary_counts_methodology_statuses_deterministically() -> None:
    first = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    observer = BacktestMethodologyObserver()
    observer.observe(_context(first, index=10))
    observer.observe(_context(first + timedelta(minutes=5), index=11))

    assert observer.summary() == {
        "ICT:NOT_CONFIRMED": 2,
        "SMC:NOT_CONFIRMED": 2,
    }
    assert (
        observer.status_count(
            MethodologyIdentifier.SMC,
            MethodologyEvaluationStatus.NOT_CONFIRMED,
        )
        == 2
    )


def test_rejects_duplicate_or_decreasing_timestamp() -> None:
    timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    observer = BacktestMethodologyObserver()
    observer.observe(_context(timestamp))

    with pytest.raises(ValueError, match="strictly increasing"):
        observer.observe(_context(timestamp, index=11))


def test_reset_clears_history_and_chronology() -> None:
    timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    observer = BacktestMethodologyObserver()
    observer.observe(_context(timestamp))

    observer.reset()

    assert observer.observations == ()
    assert observer.summary() == {}
    later = observer.observe(_context(timestamp, index=1))
    assert later.timestamp == timestamp


def test_rejects_wrong_context_type() -> None:
    with pytest.raises(TypeError, match="StrategyContext"):
        BacktestMethodologyObserver().observe(object())
