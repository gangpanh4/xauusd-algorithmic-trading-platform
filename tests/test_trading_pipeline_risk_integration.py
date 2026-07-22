from __future__ import annotations

from datetime import UTC, datetime

from core.confluence_engine.models import ConfluenceResult
from core.data.models import MarketBar
from core.risk_manager.models import RiskDecision, TradePlan
from core.trading_pipeline.config import TradingPipelineConfig
from core.trading_pipeline.pipeline import TradingPipeline


class RecordingRiskManager:
    def __init__(self) -> None:
        self.evaluate_call: dict[str, object] | None = None
        self.lifecycle_calls: list[tuple[str, object]] = []

    def evaluate_signal(self, **kwargs: object) -> TradePlan:
        self.evaluate_call = kwargs
        signal = kwargs["signal"]
        return TradePlan(
            timestamp=signal.timestamp,
            signal=signal,
            decision=RiskDecision.SKIP,
            reason="recorded",
        )

    def synchronize_account_balance(
        self,
        balance: float,
        *,
        timestamp: datetime | None = None,
    ) -> None:
        self.lifecycle_calls.append(
            ("synchronize_account_balance", (balance, timestamp))
        )

    def register_position_opened(self, count: int = 1) -> None:
        self.lifecycle_calls.append(("register_position_opened", count))

    def register_position_closed(self, count: int = 1) -> None:
        self.lifecycle_calls.append(("register_position_closed", count))

    def set_open_position_count(self, count: int) -> None:
        self.lifecycle_calls.append(("set_open_position_count", count))

    def register_completed_trade(
        self,
        pnl: float,
        *,
        timestamp: datetime | None = None,
        balance_after: float | None = None,
    ) -> None:
        self.lifecycle_calls.append(
            ("register_completed_trade", (pnl, timestamp, balance_after))
        )

    def set_emergency_stop(self, active: bool = True) -> None:
        self.lifecycle_calls.append(("set_emergency_stop", active))


def _bar(timestamp: datetime) -> MarketBar:
    return MarketBar(
        timestamp=timestamp,
        open=3300.0,
        high=3302.0,
        low=3298.0,
        close=3301.0,
        tick_volume=1_000,
    )


def test_process_bar_uses_observation_time_and_symbol_specification() -> None:
    pipeline = TradingPipeline(TradingPipelineConfig())
    recorder = RecordingRiskManager()
    pipeline.risk_manager = recorder

    observation_time = datetime(2025, 3, 14, 9, 30, tzinfo=UTC)
    confluence = ConfluenceResult(
        score=0.8,
        maximum_score=1.0,
        confidence=0.8,
        approved=True,
    )

    result = pipeline.process_bar(
        _bar(observation_time),
        confluence=confluence,
        account_balance=10_000.0,
        stop_loss_distance=2.5,
        pip_value=1.25,
        tick_size=0.01,
        lot_step=0.001,
    )

    assert recorder.evaluate_call is not None
    assert recorder.evaluate_call["signal"].timestamp == observation_time
    assert recorder.evaluate_call["tick_size"] == 0.01
    assert recorder.evaluate_call["lot_step"] == 0.001
    assert recorder.evaluate_call["pip_value"] == 1.25

    assert result.signal.timestamp == observation_time
    assert result.trade_plan.timestamp == observation_time
    assert result.confluence is confluence
    assert result.bos_event is None
    assert result.choch_event is None
    assert result.liquidity_event is None


def test_pipeline_exposes_risk_lifecycle_without_assuming_execution() -> None:
    pipeline = TradingPipeline(TradingPipelineConfig())
    recorder = RecordingRiskManager()
    pipeline.risk_manager = recorder

    timestamp = datetime(2025, 3, 14, 10, 0, tzinfo=UTC)

    pipeline.synchronize_account_balance(9_950.0, timestamp=timestamp)
    pipeline.register_position_opened(2)
    pipeline.register_position_closed()
    pipeline.set_open_position_count(1)
    pipeline.register_completed_trade(
        -50.0,
        timestamp=timestamp,
        balance_after=9_950.0,
    )
    pipeline.set_emergency_stop(True)

    assert recorder.lifecycle_calls == [
        ("synchronize_account_balance", (9_950.0, timestamp)),
        ("register_position_opened", 2),
        ("register_position_closed", 1),
        ("set_open_position_count", 1),
        ("register_completed_trade", (-50.0, timestamp, 9_950.0)),
        ("set_emergency_stop", True),
    ]


def test_historical_bar_timestamp_controls_actual_risk_session() -> None:
    from core.signal_generator.models import (
        SignalStrength,
        SignalType,
        TradingSignal,
    )

    class BuySignalGenerator:
        @staticmethod
        def generate_signal(**_: object) -> TradingSignal:
            return TradingSignal(
                signal=SignalType.BUY,
                strength=SignalStrength.STRONG,
                confidence=0.9,
                reason="forced integration signal",
            )

    pipeline = TradingPipeline(TradingPipelineConfig())
    pipeline.signal_generator = BuySignalGenerator()

    observation_time = datetime(2024, 11, 5, 15, 0, tzinfo=UTC)
    result = pipeline.process_bar(
        _bar(observation_time),
        account_balance=10_000.0,
        stop_loss_distance=2.5,
        pip_value=1.0,
        tick_size=0.01,
        lot_step=0.01,
    )

    assert result.signal.timestamp == observation_time
    assert result.trade_plan.timestamp == observation_time
    assert pipeline.risk_manager.state.current_trading_date == observation_time.date()
