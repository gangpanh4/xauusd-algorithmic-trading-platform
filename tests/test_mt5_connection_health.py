from __future__ import annotations

from types import SimpleNamespace

import pytest

import core.mt5_execution.executor as executor_module
from core.mt5_execution.config import MT5ExecutionConfig
from core.mt5_execution.executor import MT5Executor
from core.mt5_execution.models import OrderStatus


def _healthy_terminal():
    return SimpleNamespace(
        connected=True,
        trade_allowed=True,
    )


def _healthy_account():
    return SimpleNamespace(login=12345678)


def _connected_executor() -> MT5Executor:
    executor = MT5Executor(MT5ExecutionConfig())
    executor.state.initialized = True
    executor.state.connected = True
    return executor


def test_is_connected_returns_false_for_cached_disconnected_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = MT5Executor(MT5ExecutionConfig())
    monkeypatch.setattr(
        executor_module.mt5,
        "terminal_info",
        lambda: pytest.fail("terminal_info must not be called"),
    )

    assert executor.is_connected() is False


def test_is_connected_confirms_terminal_and_account_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = _connected_executor()
    monkeypatch.setattr(
        executor_module.mt5,
        "terminal_info",
        _healthy_terminal,
    )
    monkeypatch.setattr(
        executor_module.mt5,
        "account_info",
        _healthy_account,
    )

    assert executor.is_connected() is True
    assert executor.state.connected is True
    assert executor.state.error_count == 0


@pytest.mark.parametrize(
    ("terminal", "account"),
    [
        (None, _healthy_account()),
        (_healthy_terminal(), None),
        (SimpleNamespace(connected=False, trade_allowed=True), _healthy_account()),
        (SimpleNamespace(connected=True, trade_allowed=False), _healthy_account()),
    ],
)
def test_connection_health_failure_clears_stale_connected_flag(
    monkeypatch: pytest.MonkeyPatch,
    terminal,
    account,
) -> None:
    executor = _connected_executor()
    monkeypatch.setattr(
        executor_module.mt5,
        "terminal_info",
        lambda: terminal,
    )
    monkeypatch.setattr(
        executor_module.mt5,
        "account_info",
        lambda: account,
    )

    assert executor.is_connected() is False
    assert executor.state.connected is False
    assert executor.state.error_count == 1


def test_execute_order_fails_before_send_when_runtime_health_is_lost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = _connected_executor()
    monkeypatch.setattr(
        executor_module.mt5,
        "terminal_info",
        lambda: None,
    )
    monkeypatch.setattr(
        executor_module.mt5,
        "account_info",
        _healthy_account,
    )
    monkeypatch.setattr(
        executor_module,
        "send_order",
        lambda **kwargs: pytest.fail("send_order must not be called"),
    )

    with pytest.raises(RuntimeError, match="not connected"):
        executor.execute_order(object())


def test_close_position_fails_before_submission_when_runtime_health_is_lost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = _connected_executor()
    monkeypatch.setattr(
        executor_module.mt5,
        "terminal_info",
        _healthy_terminal,
    )
    monkeypatch.setattr(
        executor_module.mt5,
        "account_info",
        lambda: None,
    )
    monkeypatch.setattr(
        executor_module,
        "close_position",
        lambda **kwargs: pytest.fail("close_position must not be called"),
    )

    with pytest.raises(RuntimeError, match="not connected"):
        executor.close_position(123456)
