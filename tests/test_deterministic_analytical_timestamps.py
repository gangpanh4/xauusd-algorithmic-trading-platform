from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime, timedelta

from core.data.models import MarketBar
from core.decision_engine.engine import DecisionEngine
from core.live_trading.engine import LiveTradingEngine
from core.live_trading.state import LiveTradingState
from core.regime_detector.config import RegimeDetectorConfig
from core.regime_detector.detector import MarketRegimeDetector
from core.regime_detector.models import MarketRegime, RegimeLabel
from core.trading_pipeline.config import TradingPipelineConfig
from core.trading_pipeline.models import PipelineResult
from core.trading_pipeline.pipeline import TradingPipeline

OBSERVATION = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
AVAILABLE = OBSERVATION + timedelta(minutes=5)


def _bar() -> MarketBar:
    return MarketBar(
        timestamp=OBSERVATION,
        open=2400.0,
        high=2402.0,
        low=2398.0,
        close=2401.0,
        tick_volume=100,
    )


def _pipeline_result() -> PipelineResult:
    pipeline = TradingPipeline(TradingPipelineConfig())
    return pipeline.process_bar(
        _bar(),
        account_balance=10_000.0,
        stop_loss_distance=2.5,
        pip_value=1.0,
    )


def _without_field(value: object, field_name: str) -> tuple[tuple[str, object], ...]:
    return tuple(
        (field.name, getattr(value, field.name))
        for field in fields(value)
        if field.name != field_name
    )


def test_regime_detector_accepts_explicit_causal_computation_timestamp() -> None:
    legacy = MarketRegimeDetector(RegimeDetectorConfig()).process_bar(_bar())
    first = MarketRegimeDetector(RegimeDetectorConfig()).process_bar(
        _bar(),
        computation_timestamp=AVAILABLE,
    )
    second = MarketRegimeDetector(RegimeDetectorConfig()).process_bar(
        _bar(),
        computation_timestamp=AVAILABLE,
    )

    assert _without_field(first, "computation_timestamp") == _without_field(
        legacy,
        "computation_timestamp",
    )
    assert first.observation_timestamp == OBSERVATION
    assert second.observation_timestamp == OBSERVATION
    assert first.computation_timestamp == AVAILABLE
    assert second.computation_timestamp == AVAILABLE
    assert first == second


def test_decision_timestamp_injection_changes_only_timestamp() -> None:
    regime = MarketRegime(
        primary_regime=RegimeLabel.UNKNOWN,
        confidence=0.0,
        observation_timestamp=OBSERVATION,
        computation_timestamp=AVAILABLE,
    )

    legacy = DecisionEngine().evaluate(regime=regime)
    deterministic = DecisionEngine().evaluate(
        regime=regime,
        timestamp=AVAILABLE,
    )

    assert deterministic.timestamp == AVAILABLE
    assert _without_field(deterministic, "timestamp") == _without_field(
        legacy,
        "timestamp",
    )


def test_completed_m5_pipeline_is_repeatable_and_causal() -> None:
    first = _pipeline_result()
    second = _pipeline_result()

    for result in (first, second):
        assert result.regime.observation_timestamp == OBSERVATION
        assert result.regime.computation_timestamp == AVAILABLE
        assert result.trade_quality is not None
        assert result.trade_quality.timestamp == AVAILABLE
        assert result.decision is not None
        assert result.decision.timestamp == AVAILABLE
        assert result.signal is not None
        assert result.signal.timestamp == OBSERVATION

    assert first.regime == second.regime
    assert first.features == second.features
    assert first.probability == second.probability
    assert first.trade_quality == second.trade_quality
    assert first.confluence == second.confluence
    assert first.decision == second.decision
    assert first.signal == second.signal


def test_live_completed_m5_uses_same_timestamp_contract_as_replay() -> None:
    replay = _pipeline_result()

    live = object.__new__(LiveTradingEngine)
    live.state = LiveTradingState()
    live.pipeline = TradingPipeline(TradingPipelineConfig())
    live_result = live.process_bar(
        _bar(),
        account_balance=10_000.0,
        stop_loss_distance=2.5,
        pip_value=1.0,
        warmup=True,
    ).pipeline_result

    assert live_result.regime.observation_timestamp == OBSERVATION
    assert live_result.regime.computation_timestamp == AVAILABLE
    assert live_result.trade_quality is not None
    assert live_result.trade_quality.timestamp == AVAILABLE
    assert live_result.decision is not None
    assert live_result.decision.timestamp == AVAILABLE
    assert live_result.signal is not None
    assert live_result.signal.timestamp == OBSERVATION

    assert live_result.regime == replay.regime
    assert live_result.trade_quality == replay.trade_quality
    assert live_result.decision == replay.decision
