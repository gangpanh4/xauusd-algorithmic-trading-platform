from __future__ import annotations

from unittest.mock import Mock

from core.live_trading.config import LiveTradingConfig
from core.live_trading.engine import LiveTradingEngine


def test_live_stop_shuts_down_executor_after_connection_loss() -> None:
    engine = LiveTradingEngine(
        LiveTradingConfig(live_execution_enabled=True)
    )
    engine.state.running = True
    engine.executor.state.initialized = True
    engine.executor.state.connected = False
    engine.executor.shutdown = Mock()

    engine.stop()

    assert engine.state.running is False
    engine.executor.shutdown.assert_called_once_with()


def test_analysis_only_stop_does_not_touch_executor() -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    engine.state.running = True
    engine.executor.shutdown = Mock()

    engine.stop()

    assert engine.state.running is False
    engine.executor.shutdown.assert_not_called()
