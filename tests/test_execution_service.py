from __future__ import annotations

from unittest.mock import Mock

import pytest

from core.mt5_execution.config import MT5ExecutionConfig
from core.mt5_execution.service import ExecutionService


def test_execute_trade_delegates_to_connected_executor() -> None:
    service = ExecutionService(MT5ExecutionConfig())
    request = object()
    expected = object()
    service.executor.execute_order = Mock(return_value=expected)

    result = service.execute_trade(request)

    assert result is expected
    service.executor.execute_order.assert_called_once_with(request)


def test_execute_trade_preserves_executor_fail_closed_behavior() -> None:
    service = ExecutionService(MT5ExecutionConfig())
    service.executor.execute_order = Mock(
        side_effect=RuntimeError("MT5Executor is not connected.")
    )

    with pytest.raises(RuntimeError, match="not connected"):
        service.execute_trade(object())


def test_initialize_delegates_to_executor() -> None:
    service = ExecutionService(MT5ExecutionConfig())
    service.executor.initialize = Mock(return_value=True)

    assert service.initialize() is True
    service.executor.initialize.assert_called_once_with()


def test_shutdown_delegates_to_executor() -> None:
    service = ExecutionService(MT5ExecutionConfig())
    service.executor.shutdown = Mock()

    service.shutdown()

    service.executor.shutdown.assert_called_once_with()
