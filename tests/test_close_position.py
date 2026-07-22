from __future__ import annotations

from types import SimpleNamespace

import pytest

import core.mt5_execution.close_position as close_module
import core.mt5_execution.executor as executor_module
from core.mt5_execution.config import MT5ExecutionConfig
from core.mt5_execution.executor import MT5Executor
from core.mt5_execution.models import (
    OrderSide,
    OrderStatus,
    PositionInfo,
    SymbolInfo,
)


def _position(
    *,
    side: OrderSide = OrderSide.BUY,
    volume: float = 0.01,
) -> PositionInfo:
    return PositionInfo(
        ticket=123456,
        symbol="XAUUSD",
        side=side,
        volume=volume,
        open_price=3300.0,
        stop_loss=3295.0,
        take_profit=3310.0,
        profit=10.0,
    )


def _symbol(
    *,
    flags: int = 1,
    execution_mode: int = 2,
) -> SymbolInfo:
    return SymbolInfo(
        name="XAUUSD",
        digits=2,
        point=0.01,
        spread=20,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        trade_allowed=True,
        tick_size=0.01,
        minimum_stop_distance=0.01,
        filling_mode_flags=flags,
        trade_execution_mode=execution_mode,
    )


def _prepare(
    monkeypatch: pytest.MonkeyPatch,
    *,
    position: PositionInfo | None = None,
    symbol: SymbolInfo | None = None,
) -> None:
    monkeypatch.setattr(
        close_module,
        "get_position",
        lambda ticket: _position() if position is None else position,
    )
    monkeypatch.setattr(
        close_module,
        "get_symbol_info",
        lambda name: _symbol() if symbol is None else symbol,
    )


def test_missing_position_fails_before_broker_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(close_module, "get_position", lambda ticket: None)
    calls: list[str] = []
    monkeypatch.setattr(
        close_module.mt5,
        "order_check",
        lambda request: calls.append("check"),
    )
    monkeypatch.setattr(
        close_module.mt5,
        "order_send",
        lambda request: calls.append("send"),
    )

    result = close_module.close_position(
        123456,
        MT5ExecutionConfig(),
    )

    assert result.status is OrderStatus.REJECTED
    assert result.message == "Position not found."
    assert calls == []


@pytest.mark.parametrize(
    ("side", "expected_type", "expected_price"),
    [
        (OrderSide.BUY, "sell", 3299.75),
        (OrderSide.SELL, "buy", 3300.25),
    ],
)
def test_close_uses_opposite_side_and_executable_price(
    monkeypatch: pytest.MonkeyPatch,
    side: OrderSide,
    expected_type: str,
    expected_price: float,
) -> None:
    _prepare(monkeypatch, position=_position(side=side))
    monkeypatch.setattr(
        close_module.mt5,
        "symbol_info_tick",
        lambda name: SimpleNamespace(bid=3299.75, ask=3300.25),
    )
    monkeypatch.setattr(
        close_module.mt5,
        "order_check",
        lambda request: SimpleNamespace(retcode=0, comment="Done"),
    )

    captured: dict = {}

    def fake_send(request):
        captured.update(request)
        return SimpleNamespace(
            retcode=close_module.mt5.TRADE_RETCODE_DONE,
            order=777,
            price=request["price"],
            volume=request["volume"],
            comment="closed",
        )

    monkeypatch.setattr(close_module.mt5, "order_send", fake_send)

    result = close_module.close_position(
        123456,
        MT5ExecutionConfig(),
    )

    expected_mt5_type = (
        close_module.mt5.ORDER_TYPE_SELL
        if expected_type == "sell"
        else close_module.mt5.ORDER_TYPE_BUY
    )
    assert result.status is OrderStatus.FILLED
    assert captured["type"] == expected_mt5_type
    assert captured["price"] == pytest.approx(expected_price)
    assert captured["position"] == 123456
    assert captured["volume"] == pytest.approx(0.01)


def test_close_preflight_rejection_prevents_submission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare(monkeypatch)
    monkeypatch.setattr(
        close_module.mt5,
        "symbol_info_tick",
        lambda name: SimpleNamespace(bid=3299.75, ask=3300.25),
    )
    monkeypatch.setattr(
        close_module.mt5,
        "order_check",
        lambda request: SimpleNamespace(
            retcode=10016,
            comment="Invalid stops",
        ),
    )
    sends: list[dict] = []
    monkeypatch.setattr(
        close_module.mt5,
        "order_send",
        lambda request: sends.append(request),
    )

    result = close_module.close_position(
        123456,
        MT5ExecutionConfig(),
    )

    assert result.status is OrderStatus.REJECTED
    assert result.retcode == 10016
    assert "Close preflight rejected [10016]" in result.message
    assert sends == []


def test_partial_close_result_is_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare(monkeypatch)
    monkeypatch.setattr(
        close_module.mt5,
        "symbol_info_tick",
        lambda name: SimpleNamespace(bid=3299.75, ask=3300.25),
    )
    monkeypatch.setattr(
        close_module.mt5,
        "order_check",
        lambda request: SimpleNamespace(retcode=0, comment="Done"),
    )
    monkeypatch.setattr(
        close_module.mt5,
        "order_send",
        lambda request: SimpleNamespace(
            retcode=getattr(
                close_module.mt5,
                "TRADE_RETCODE_DONE_PARTIAL",
                10010,
            ),
            order=888,
            price=request["price"],
            volume=0.005,
            comment="partially closed",
        ),
    )

    result = close_module.close_position(
        123456,
        MT5ExecutionConfig(),
    )

    assert result.status is OrderStatus.PARTIALLY_FILLED
    assert result.executed_volume == pytest.approx(0.005)


def test_unsupported_filling_mode_fails_before_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    market_execution = getattr(
        close_module.mt5,
        "SYMBOL_TRADE_EXECUTION_MARKET",
        2,
    )
    _prepare(
        monkeypatch,
        symbol=_symbol(flags=0, execution_mode=market_execution),
    )
    monkeypatch.setattr(
        close_module.mt5,
        "symbol_info_tick",
        lambda name: SimpleNamespace(bid=3299.75, ask=3300.25),
    )
    checks: list[dict] = []
    monkeypatch.setattr(
        close_module.mt5,
        "order_check",
        lambda request: checks.append(request),
    )

    result = close_module.close_position(
        123456,
        MT5ExecutionConfig(),
    )

    assert result.status is OrderStatus.REJECTED
    assert "No supported filling mode" in result.message
    assert checks == []


def test_executor_requires_connection_before_closing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = MT5Executor(MT5ExecutionConfig())
    close_mock = lambda **kwargs: pytest.fail(
        "close_position must not be called"
    )
    monkeypatch.setattr(executor_module, "close_position", close_mock)

    with pytest.raises(RuntimeError, match="not connected"):
        executor.close_position(123456)


def test_executor_delegates_close_when_connected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = MT5Executor(MT5ExecutionConfig())
    executor.state.connected = True
    expected = SimpleNamespace(status=OrderStatus.FILLED)

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

    captured: dict = {}

    def fake_close(**kwargs):
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(executor_module, "close_position", fake_close)

    result = executor.close_position(123456)

    assert result is expected
    assert captured == {
        "ticket": 123456,
        "config": executor.config,
    }
