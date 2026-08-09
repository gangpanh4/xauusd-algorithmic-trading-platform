from __future__ import annotations

from pathlib import Path

import pytest

import core.mt5_execution.close_position as close_module
import core.mt5_execution.orders as orders_module
from core.mt5_execution.authority import (
    BrokerMutationAuthorityError,
    _authorize_broker_mutation,
    _require_broker_mutation_authority,
)
from core.mt5_execution.config import MT5ExecutionConfig
from core.mt5_execution.executor import MT5Executor
from core.mt5_execution.service import ExecutionService


def test_authority_scope_resets_after_exit() -> None:
    with pytest.raises(BrokerMutationAuthorityError, match="restricted"):
        _require_broker_mutation_authority()

    with _authorize_broker_mutation():
        _require_broker_mutation_authority()

    with pytest.raises(BrokerMutationAuthorityError, match="restricted"):
        _require_broker_mutation_authority()


def test_direct_send_order_fails_before_broker_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        orders_module,
        "get_symbol_info",
        lambda symbol: pytest.fail("symbol query must not run"),
    )
    monkeypatch.setattr(
        orders_module.mt5,
        "order_send",
        lambda request: pytest.fail("order_send must not run"),
    )

    with pytest.raises(BrokerMutationAuthorityError, match="restricted"):
        orders_module.send_order(object(), MT5ExecutionConfig())


def test_direct_close_position_fails_before_broker_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        close_module,
        "get_position",
        lambda ticket: pytest.fail("position query must not run"),
    )
    monkeypatch.setattr(
        close_module.mt5,
        "order_send",
        lambda request: pytest.fail("order_send must not run"),
    )

    with pytest.raises(BrokerMutationAuthorityError, match="restricted"):
        close_module.close_position(123456, MT5ExecutionConfig())


@pytest.mark.parametrize("method_name", ["execute_order", "close_position"])
def test_direct_executor_mutation_fails_before_connection_check(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
) -> None:
    executor = MT5Executor(MT5ExecutionConfig())
    monkeypatch.setattr(
        executor,
        "is_connected",
        lambda: pytest.fail("connection check must not run"),
    )

    method = getattr(executor, method_name)
    with pytest.raises(BrokerMutationAuthorityError, match="restricted"):
        method(object() if method_name == "execute_order" else 123456)


def test_direct_execution_service_fails_before_executor_delegation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ExecutionService(MT5ExecutionConfig())
    monkeypatch.setattr(
        service.executor,
        "execute_order",
        lambda request: pytest.fail("executor must not run"),
    )

    with pytest.raises(BrokerMutationAuthorityError, match="restricted"):
        service.execute_trade(object())


def test_only_live_engine_opens_production_mutation_authority() -> None:
    project_root = Path(__file__).resolve().parents[1]
    callers = {
        path.relative_to(project_root).as_posix()
        for path in (project_root / "core").rglob("*.py")
        if path.name != "authority.py"
        and "_authorize_broker_mutation" in path.read_text(encoding="utf-8")
    }

    assert callers == {"core/live_trading/engine.py"}
