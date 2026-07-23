from __future__ import annotations

from unittest.mock import Mock

from core.live_trading.config import LiveTradingConfig
from core.live_trading.engine import LiveTradingEngine


def test_live_stop_detaches_without_shutting_down_shared_mt5() -> None:
    engine = LiveTradingEngine(
        LiveTradingConfig(live_execution_enabled=True)
    )
    engine.state.running = True
    engine.executor.detach = Mock()
    engine.executor.shutdown = Mock()

    engine.stop()

    assert engine.state.running is False
    engine.executor.detach.assert_called_once_with()
    engine.executor.shutdown.assert_not_called()


def test_analysis_only_stop_does_not_touch_executor() -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    engine.state.running = True
    engine.executor.detach = Mock()
    engine.executor.shutdown = Mock()

    engine.stop()

    assert engine.state.running is False
    engine.executor.detach.assert_not_called()
    engine.executor.shutdown.assert_not_called()
