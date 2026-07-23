from __future__ import annotations

from types import SimpleNamespace

import pytest

import core.mt5_execution.executor as executor_module
from core.mt5_execution.config import MT5ExecutionConfig
from core.mt5_execution.executor import MT5Executor


def test_initialize_success_sets_connected_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = MT5Executor(MT5ExecutionConfig())
    monkeypatch.setattr(
        executor_module.mt5,
        "initialize",
        lambda: True,
    )

    assert executor.initialize() is True
    assert executor.state.initialized is True
    assert executor.state.connected is True
    assert executor.state.last_connection_time is not None
    assert executor.state.error_count == 0


def test_initialize_failure_keeps_executor_disconnected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = MT5Executor(MT5ExecutionConfig())
    monkeypatch.setattr(
        executor_module.mt5,
        "initialize",
        lambda: False,
    )

    assert executor.initialize() is False
    assert executor.state.initialized is False
    assert executor.state.connected is False
    assert executor.state.last_connection_time is None
    assert executor.state.error_count == 1


def test_shutdown_calls_mt5_and_clears_connection_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = MT5Executor(MT5ExecutionConfig())
    executor.state.initialized = True
    executor.state.connected = True
    calls: list[str] = []

    monkeypatch.setattr(
        executor_module.mt5,
        "shutdown",
        lambda: calls.append("shutdown"),
    )

    executor.shutdown()

    assert calls == ["shutdown"]
    assert executor.state.initialized is False
    assert executor.state.connected is False
    assert executor.state.last_disconnection_time is not None


def test_is_connected_rejects_terminal_without_trade_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = MT5Executor(MT5ExecutionConfig())
    executor.state.initialized = True
    executor.state.connected = True

    monkeypatch.setattr(
        executor_module.mt5,
        "terminal_info",
        lambda: SimpleNamespace(
            connected=True,
            trade_allowed=False,
        ),
    )
    monkeypatch.setattr(
        executor_module.mt5,
        "account_info",
        lambda: SimpleNamespace(login=12345678),
    )

    assert executor.is_connected() is False
    assert executor.state.connected is False
    assert executor.state.error_count == 1


def test_attach_uses_existing_healthy_mt5_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = MT5Executor(MT5ExecutionConfig())
    initialize_calls: list[str] = []

    monkeypatch.setattr(
        executor_module.mt5,
        "terminal_info",
        lambda: SimpleNamespace(
            connected=True,
            trade_allowed=True,
        ),
    )
    monkeypatch.setattr(
        executor_module.mt5,
        "account_info",
        lambda: SimpleNamespace(login=12345678),
    )
    monkeypatch.setattr(
        executor_module.mt5,
        "initialize",
        lambda: initialize_calls.append("initialize"),
    )

    assert executor.attach() is True
    assert executor.state.initialized is True
    assert executor.state.connected is True
    assert initialize_calls == []


def test_attach_failure_keeps_executor_disconnected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = MT5Executor(MT5ExecutionConfig())
    monkeypatch.setattr(
        executor_module.mt5,
        "terminal_info",
        lambda: None,
    )
    monkeypatch.setattr(
        executor_module.mt5,
        "account_info",
        lambda: None,
    )

    assert executor.attach() is False
    assert executor.state.initialized is False
    assert executor.state.connected is False
    assert executor.state.error_count == 1


def test_detach_clears_state_without_mt5_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = MT5Executor(MT5ExecutionConfig())
    executor.state.initialized = True
    executor.state.connected = True
    shutdown_calls: list[str] = []
    monkeypatch.setattr(
        executor_module.mt5,
        "shutdown",
        lambda: shutdown_calls.append("shutdown"),
    )

    executor.detach()

    assert executor.state.initialized is False
    assert executor.state.connected is False
    assert executor.state.last_disconnection_time is not None
    assert shutdown_calls == []
