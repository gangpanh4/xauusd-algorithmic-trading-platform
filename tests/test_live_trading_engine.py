from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.live_trading.config import LiveTradingConfig
from core.live_trading.engine import LiveTradingEngine
from core.regime_detector.models import MarketBar
from core.risk_manager.models import RiskDecision


def _market_bar() -> MarketBar:
    return MarketBar(
        timestamp=datetime.now(UTC),
        open=4000.0,
        high=4005.0,
        low=3998.0,
        close=4003.0,
        volume=1000,
    )


def _approved_pipeline_result() -> SimpleNamespace:
    trade_plan = SimpleNamespace(
        decision=RiskDecision.APPROVE,
        entry_price=4003.0,
        stop_loss=4001.0,
        take_profit=4007.0,
        position_size=0.01,
    )
    signal = SimpleNamespace(direction="BUY")
    return SimpleNamespace(
        signal=signal,
        trade_plan=trade_plan,
    )


def test_disabled_engine_processes_bars_without_initializing_mt5() -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    engine.executor.initialize = Mock(return_value=True)

    engine.start()

    assert engine.state.running is True
    engine.executor.initialize.assert_not_called()


def test_disabled_engine_never_executes_approved_trade() -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    pipeline_result = _approved_pipeline_result()

    engine.pipeline.process_bar = Mock(return_value=pipeline_result)
    engine.adapter.adapt = Mock()
    engine.executor.execute_order = Mock()

    engine.start()
    result = engine.process_bar(
        _market_bar(),
        account_balance=1000.0,
        stop_loss_distance=2.0,
        pip_value=1.0,
    )

    assert result.pipeline_result is pipeline_result
    assert result.execution_result is None
    assert result.trade_executed is False
    assert engine.state.executed_trades == 0
    assert engine.state.skipped_trades == 1
    engine.adapter.adapt.assert_not_called()
    engine.executor.execute_order.assert_not_called()


def test_disabled_engine_stop_does_not_shutdown_mt5() -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    engine.executor.shutdown = Mock()

    engine.start()
    engine.stop()

    assert engine.state.running is False
    engine.executor.shutdown.assert_not_called()


def test_enabled_engine_fails_closed_when_mt5_attachment_fails() -> None:
    config = LiveTradingConfig(live_execution_enabled=True)
    engine = LiveTradingEngine(config)
    engine.executor.attach = Mock(return_value=False)

    with pytest.raises(
        RuntimeError,
        match="Failed to attach MT5 execution",
    ):
        engine.start()

    assert engine.state.running is False
    assert engine.state.last_error == "Failed to attach MT5 execution."


def test_live_trading_engine_contract() -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    engine.start()

    bar = _market_bar()
    result = engine.process_bar(
        bar,
        account_balance=1000.0,
        stop_loss_distance=2.0,
        pip_value=1.0,
    )

    assert result is not None
    assert result.pipeline_result is not None

    trade_plan = result.pipeline_result.trade_plan

    assert trade_plan is not None
    assert hasattr(trade_plan, "entry_price")

    if trade_plan.decision.value == "APPROVE":
        assert trade_plan.entry_price == bar.close
        assert trade_plan.stop_loss != 0
        assert trade_plan.take_profit != 0
        assert trade_plan.position_size > 0
        assert result.trade_executed is False
    else:
        assert trade_plan.entry_price == 0.0
        assert trade_plan.stop_loss == 0.0
        assert trade_plan.take_profit == 0.0
        assert trade_plan.position_size == 0.0
