from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from core.backtesting.config import BacktestConfig, BacktestExecutionModel
from core.backtesting.engine import BacktestingEngine
from core.feature_engineering.models import FeatureVector
from core.regime_detector.models import MarketBar
from core.risk_manager.models import RiskDecision, TradePlan
from core.signal_generator.models import SignalDirection, TradingSignal
from core.trading_pipeline.market_context import MarketContext

START = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)


def _bar(
    minute: int,
    *,
    open_price: float = 100.0,
    high: float = 101.0,
    low: float = 99.0,
    close: float = 100.0,
) -> MarketBar:
    return MarketBar(
        timestamp=START + timedelta(minutes=minute),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=100.0,
        tick_volume=100,
    )


class _Pipeline:
    def __init__(self) -> None:
        self.calls = 0
        self.opened = 0
        self.closed = 0

    def synchronize_account_balance(
        self,
        balance: float,
        *,
        timestamp: datetime | None = None,
    ) -> None:
        del balance, timestamp

    def process_bar(self, bar: MarketBar, **_: object) -> SimpleNamespace:
        self.calls += 1
        approved = self.calls == 1
        signal = TradingSignal(
            timestamp=bar.timestamp,
            direction=(SignalDirection.BUY if approved else SignalDirection.HOLD),
        )
        plan = TradePlan(
            timestamp=bar.timestamp,
            signal=signal,
            decision=(RiskDecision.APPROVE if approved else RiskDecision.SKIP),
            position_size=0.1 if approved else 0.0,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            risk_reward_ratio=2.0,
            probability=0.7,
            confidence=0.8,
            feature_count=0,
            evidence_count=0,
            regime="TEST",
        )
        return SimpleNamespace(
            signal=signal,
            trade_plan=plan,
            trade_quality=None,
            features=FeatureVector(),
        )

    def register_position_opened(self, count: int = 1) -> None:
        self.opened += count

    def register_position_closed(self, count: int = 1) -> None:
        self.closed += count

    def register_completed_trade(self, *args: object, **kwargs: object) -> None:
        del args, kwargs


def _context(
    *,
    m5_bars: list[MarketBar],
    m15_bars: list[MarketBar] | None = None,
) -> MarketContext:
    m15 = m15_bars or [_bar(0), _bar(15), _bar(30)]
    return MarketContext(
        current_bar=m5_bars[-1],
        m5_bars=m5_bars,
        m15_bars=m15,
        h1_bars=m15,
        h4_bars=m15,
    )


def _engine(model: BacktestExecutionModel) -> BacktestingEngine:
    engine = BacktestingEngine(
        BacktestConfig(
            execution_model=model,
            warmup_bars=0,
            maximum_trades=1,
        ),
        tick_size=0.01,
        tick_value_per_lot=1.0,
        progress_interval_bars=None,
    )
    pipeline = _Pipeline()
    engine._create_pipeline = lambda: pipeline  # type: ignore[method-assign]
    return engine


def test_v2_eligibility_starts_at_decision_availability() -> None:
    engine = _engine(BacktestExecutionModel.M5_COMPLETED_OHLC_V2)
    observation = _bar(0)

    assert not engine._execution_bar_is_eligible(
        observation_bar=observation,
        execution_bar=_bar(0),
    )
    assert engine._execution_bar_is_eligible(
        observation_bar=observation,
        execution_bar=_bar(5),
    )
    assert engine._execution_bar_is_eligible(
        observation_bar=observation,
        execution_bar=_bar(10),
    )


def test_v2_uses_first_available_m5_after_decision_and_never_fabricates_gap() -> None:
    m5 = [
        _bar(0),
        # 10:05 is intentionally missing.
        _bar(10, open_price=101.0, high=112.0, low=100.0, close=111.0),
        _bar(15),
    ]
    result = _engine(BacktestExecutionModel.M5_COMPLETED_OHLC_V2).run(
        _context(m5_bars=m5)
    )

    assert result.total_trades == 1
    trade = result.trades[0]
    assert trade.entry_time == START + timedelta(minutes=10)
    assert trade.exit_time == START + timedelta(minutes=10)
    assert trade.metadata["execution_model_id"] == "M5_COMPLETED_OHLC_V2"
    assert trade.metadata["entry_clock"] == "M5"
    assert trade.metadata["lifecycle_clock"] == "M5_COMPLETED"


def test_v2_uses_next_m5_open_and_evaluates_that_bar_only_as_completed_lifecycle() -> None:
    m5 = [
        _bar(0),
        _bar(5, open_price=101.0, high=112.0, low=100.0, close=111.0),
        _bar(10),
    ]
    # If the containing M15 candle were accidentally used by V2, its extreme
    # low would force a different outcome. V2 must consume only completed M5.
    m15 = [
        _bar(0, open_price=100.0, high=1000.0, low=1.0, close=100.0),
        _bar(15),
    ]

    result = _engine(BacktestExecutionModel.M5_COMPLETED_OHLC_V2).run(
        _context(m5_bars=m5, m15_bars=m15)
    )

    trade = result.trades[0]
    assert trade.entry_time == START + timedelta(minutes=5)
    assert trade.exit_time == START + timedelta(minutes=5)
    metadata = trade.metadata
    # Group 3 execution-model provenance is authoritative independently of
    # whether a Group 2 ExecutionEconomicsProfile is attached to the engine.
    # The 10:05 open is the entry reference, while that bar's OHLC lifecycle
    # is only information-available after the bar completes at 10:10.
    assert metadata["decision_available_at"] == (
        START + timedelta(minutes=5)
    ).isoformat()
    assert metadata["entry_reference_timestamp"] == (
        START + timedelta(minutes=5)
    ).isoformat()
    assert metadata["entry_bar_completed_at"] == (
        START + timedelta(minutes=10)
    ).isoformat()
    assert metadata["first_lifecycle_evaluation_available_at"] == (
        START + timedelta(minutes=10)
    ).isoformat()
    assert metadata["execution_model_id"] == "M5_COMPLETED_OHLC_V2"
    assert metadata["entry_policy"] == "NEXT_AVAILABLE_M5_OPEN"
    assert metadata["entry_clock"] == "M5"
    assert metadata["lifecycle_clock"] == "M5_COMPLETED"
    assert metadata["closed_bar_consumption"] == "ONLY_AFTER_BAR_COMPLETES"
    assert metadata["lifecycle_bar_minutes"] == 5
    assert metadata["same_bar_entry_exit_evaluation"] is True


def test_v1_and_v2_produce_distinct_entry_clocks_on_same_history() -> None:
    m5 = [
        _bar(0),
        _bar(5, open_price=101.0, high=102.0, low=100.0, close=101.0),
        _bar(10),
        _bar(15),
        _bar(20),
        _bar(25),
        _bar(30),
    ]
    m15 = [
        _bar(0),
        _bar(15, open_price=103.0, high=114.0, low=102.0, close=113.0),
        _bar(30),
    ]
    context = _context(m5_bars=m5, m15_bars=m15)

    v1 = _engine(BacktestExecutionModel.M15_COMPLETED_OHLC_V1).run(context)
    v2 = _engine(BacktestExecutionModel.M5_COMPLETED_OHLC_V2).run(context)

    assert v1.trades[0].entry_time == START + timedelta(minutes=15)
    assert v2.trades[0].entry_time == START + timedelta(minutes=5)
    assert v1.trades[0].metadata["execution_model_id"] == "M15_COMPLETED_OHLC_V1"
    assert v2.trades[0].metadata["execution_model_id"] == "M5_COMPLETED_OHLC_V2"
