from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from core.backtesting.config import BacktestConfig
from core.backtesting.engine import BacktestingEngine
from core.feature_engineering.models import FeatureVector
from core.regime_detector.models import MarketBar
from core.signal_generator.models import SignalDirection, TradingSignal
from core.trading_pipeline.market_context import MarketContext
from core.trading_pipeline.models import (
    PipelineDisposition,
    PipelineObservationAudit,
    PipelineStage,
)


BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def _bar(index: int) -> MarketBar:
    return MarketBar(
        timestamp=BASE_TIME + timedelta(minutes=15 * index),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=100.0,
        tick_volume=100,
    )


def _context(bars: list[MarketBar]) -> MarketContext:
    return MarketContext(
        current_bar=bars[-1],
        m5_bars=bars,
        m15_bars=bars,
        h1_bars=bars,
        h4_bars=bars,
    )


class AuditPipeline:
    def __init__(self, *, timestamp_offset: timedelta = timedelta(0)) -> None:
        self.timestamp_offset = timestamp_offset
        self.last_observation_audit: PipelineObservationAudit | None = None
        self.calls = 0

    def synchronize_account_balance(self, *_: object, **__: object) -> None:
        return None

    def process_bar(self, bar: MarketBar, **_: object) -> SimpleNamespace:
        self.calls += 1
        code = "REGIME_UNCONFIRMED" if self.calls < 3 else "SIGNAL_NOT_GENERATED"
        stage = PipelineStage.REGIME if self.calls < 3 else PipelineStage.SIGNAL
        self.last_observation_audit = PipelineObservationAudit(
            timestamp=bar.timestamp + self.timestamp_offset,
            disposition=PipelineDisposition.REJECTED,
            stage_reached=PipelineStage.RISK,
            rejection_stage=stage,
            reason_code=code,
            reason="diagnostic rejection",
        )
        return SimpleNamespace(
            signal=TradingSignal(
                timestamp=bar.timestamp,
                direction=SignalDirection.HOLD,
            ),
            trade_plan=None,
            trade_quality=None,
            features=FeatureVector(),
        )

    def register_position_opened(self, count: int = 1) -> None:
        del count

    def register_position_closed(self, count: int = 1) -> None:
        del count

    def register_completed_trade(self, *_: object, **__: object) -> None:
        return None


def _engine(pipeline: AuditPipeline) -> BacktestingEngine:
    engine = BacktestingEngine(
        BacktestConfig(warmup_bars=0, maximum_trades=None),
        progress_interval_bars=None,
    )
    engine._create_pipeline = lambda: pipeline  # type: ignore[method-assign]
    return engine


def test_engine_collects_one_audit_per_processed_observation() -> None:
    bars = [_bar(index) for index in range(4)]
    engine = _engine(AuditPipeline())

    result = engine.run(_context(bars))

    assert result.total_trades == 0
    assert len(engine.observation_audits) == len(bars)
    assert [audit.timestamp for audit in engine.observation_audits] == [
        bar.timestamp for bar in bars
    ]


def test_observation_audit_summary_counts_rejection_codes() -> None:
    bars = [_bar(index) for index in range(4)]
    engine = _engine(AuditPipeline())

    engine.run(_context(bars))

    assert engine.observation_audit_summary() == {
        "REGIME_UNCONFIRMED": 2,
        "SIGNAL_NOT_GENERATED": 2,
    }


def test_observation_audits_are_exposed_as_immutable_tuple_and_reset() -> None:
    bars = [_bar(index) for index in range(2)]
    engine = _engine(AuditPipeline())

    engine.run(_context(bars))
    audits = engine.observation_audits

    assert isinstance(audits, tuple)
    assert len(audits) == 2

    engine.reset()
    assert engine.observation_audits == ()
    assert engine.observation_audit_summary() == {}


def test_engine_rejects_audit_timestamp_mismatch() -> None:
    bars = [_bar(index) for index in range(2)]
    engine = _engine(AuditPipeline(timestamp_offset=timedelta(seconds=1)))

    with pytest.raises(ValueError, match="timestamp does not match"):
        engine.run(_context(bars))
