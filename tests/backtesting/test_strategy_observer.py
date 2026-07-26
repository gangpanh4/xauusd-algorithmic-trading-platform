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
from core.regime_detector.models import MarketRegime, RegimeLabel
from core.strategies import StrategyObservation


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


def _regime(timestamp: datetime) -> MarketRegime:
    return MarketRegime(
        primary_regime=RegimeLabel.TRENDING_BULL,
        confidence=0.80,
        observation_timestamp=timestamp,
        computation_timestamp=timestamp,
    )


class _StateRecorder:
    def __init__(self) -> None:
        self.observations: list[StrategyObservation] = []

    def observation_summary(self) -> dict[str, int]:
        summary: dict[str, int] = {}
        for observation in self.observations:
            summary[observation.reason_code] = (
                summary.get(observation.reason_code, 0) + 1
            )
        return summary


class _CapturingStrategy:
    def __init__(self) -> None:
        self.state = _StateRecorder()
        self.contexts = []

    def reset(self) -> None:
        self.state.observations.clear()
        self.contexts.clear()

    def observe(self, context):
        self.contexts.append(context)
        observation = StrategyObservation(
            timestamp=context.current_bar.timestamp,
            setup=None,
            trigger=None,
            candidate_trade=None,
            reason_code="NO_SETUP",
            reason="No setup.",
        )
        self.state.observations.append(observation)
        return observation


def test_observer_records_strategy_results_without_trade_authorization() -> None:
    observer = BacktestStrategyObserver()
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)

    observation = observer.observe(
        multi_timeframe=_mtf(timestamp),
        current_bar=_bar(timestamp),
        current_bar_index=10,
    )

    assert observation.reason_code == "NO_SETUP"
    assert observation.candidate_trade is None
    assert observer.candidate_count == 0
    assert observer.observation_summary() == {"NO_SETUP": 1}
    assert observer.observations == (observation,)


def test_observer_supplies_same_candle_regime_to_strategy_context() -> None:
    strategy = _CapturingStrategy()
    observer = BacktestStrategyObserver(strategy=strategy)
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    regime = _regime(timestamp)

    observer.observe(
        multi_timeframe=_mtf(timestamp),
        current_bar=_bar(timestamp),
        current_bar_index=10,
        market_regime=regime,
    )

    assert len(strategy.contexts) == 1
    context = strategy.contexts[0]
    assert context.market_regime is regime
    assert context.market_regime.observation_timestamp == timestamp


@pytest.mark.parametrize("offset_minutes", [-5, 5])
def test_observer_rejects_stale_or_future_regime(
    offset_minutes: int,
) -> None:
    observer = BacktestStrategyObserver(strategy=_CapturingStrategy())
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    mismatched = _regime(timestamp + timedelta(minutes=offset_minutes))

    with pytest.raises(ValueError, match="must match current_bar timestamp"):
        observer.observe(
            multi_timeframe=_mtf(timestamp),
            current_bar=_bar(timestamp),
            current_bar_index=10,
            market_regime=mismatched,
        )


def test_observer_rejects_wrong_regime_type() -> None:
    observer = BacktestStrategyObserver(strategy=_CapturingStrategy())
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)

    with pytest.raises(TypeError, match="MarketRegime or None"):
        observer.observe(
            multi_timeframe=_mtf(timestamp),
            current_bar=_bar(timestamp),
            current_bar_index=10,
            market_regime=object(),
        )


def test_observer_rejects_duplicate_timestamp_and_index() -> None:
    observer = BacktestStrategyObserver()
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)

    observer.observe(
        multi_timeframe=_mtf(timestamp),
        current_bar=_bar(timestamp),
        current_bar_index=10,
    )

    with pytest.raises(ValueError, match="timestamps"):
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
    assert observation.reason_code == "NO_SETUP"
