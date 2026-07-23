from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

import core.mt5_execution.executor as executor_module
from core.mt5_execution.config import MT5ExecutionConfig
from core.mt5_execution.executor import MT5Executor
from core.mt5_execution.models import OrderResult, OrderStatus


def _healthy_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> MT5Executor:
    executor = MT5Executor(MT5ExecutionConfig())
    executor.state.initialized = True
    executor.state.connected = True

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
    return executor


def _result(status: OrderStatus) -> OrderResult:
    return OrderResult(
        timestamp=datetime.now(UTC),
        status=status,
        ticket=123 if status is not OrderStatus.REJECTED else None,
        executed_price=3300.0,
        message=status.value,
    )


@pytest.mark.parametrize(
    "status",
    [
        OrderStatus.FILLED,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.PENDING,
        OrderStatus.CANCELLED,
    ],
)
def test_execute_order_records_non_rejected_result(
    monkeypatch: pytest.MonkeyPatch,
    status: OrderStatus,
) -> None:
    executor = _healthy_executor(monkeypatch)
    expected = _result(status)
    monkeypatch.setattr(
        executor_module,
        "send_order",
        lambda **kwargs: expected,
    )

    result = executor.execute_order(object())

    assert result is expected
    assert executor.state.last_order is expected
    assert executor.state.total_orders_sent == 1
    assert executor.state.error_count == 0


def test_execute_order_records_rejection_as_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = _healthy_executor(monkeypatch)
    expected = _result(OrderStatus.REJECTED)
    monkeypatch.setattr(
        executor_module,
        "send_order",
        lambda **kwargs: expected,
    )

    result = executor.execute_order(object())

    assert result is expected
    assert executor.state.last_order is expected
    assert executor.state.total_orders_sent == 1
    assert executor.state.error_count == 1


def test_execute_order_exception_increments_error_without_false_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = _healthy_executor(monkeypatch)
    monkeypatch.setattr(
        executor_module,
        "send_order",
        lambda **kwargs: (_ for _ in ()).throw(
            RuntimeError("submission failure")
        ),
    )

    with pytest.raises(RuntimeError, match="submission failure"):
        executor.execute_order(object())

    assert executor.state.last_order is None
    assert executor.state.total_orders_sent == 0
    assert executor.state.error_count == 1


def test_close_position_uses_same_state_accounting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = _healthy_executor(monkeypatch)
    expected = _result(OrderStatus.FILLED)
    monkeypatch.setattr(
        executor_module,
        "close_position",
        lambda **kwargs: expected,
    )

    result = executor.close_position(123456)

    assert result is expected
    assert executor.state.last_order is expected
    assert executor.state.total_orders_sent == 1
    assert executor.state.error_count == 0


def test_multiple_execution_results_accumulate_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = _healthy_executor(monkeypatch)
    results = iter(
        [
            _result(OrderStatus.FILLED),
            _result(OrderStatus.REJECTED),
        ]
    )
    monkeypatch.setattr(
        executor_module,
        "send_order",
        lambda **kwargs: next(results),
    )

    first = executor.execute_order(object())
    second = executor.execute_order(object())

    assert executor.state.total_orders_sent == 2
    assert executor.state.last_order is second
    assert executor.state.last_order is not first
    assert executor.state.error_count == 1
