from __future__ import annotations

from types import SimpleNamespace

import pytest

import core.mt5_execution.active_orders as active_orders


def test_active_order_count_uses_exact_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_orders_get(**kwargs):
        captured.update(kwargs)
        return (SimpleNamespace(ticket=1), SimpleNamespace(ticket=2))

    monkeypatch.setattr(active_orders.mt5, "orders_get", fake_orders_get)

    assert active_orders.get_active_order_count("XAUUSD.a") == 2
    assert captured == {"symbol": "XAUUSD.a"}


def test_active_order_query_failure_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        active_orders.mt5,
        "orders_get",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        active_orders.mt5,
        "last_error",
        lambda: (-10004, "No IPC connection"),
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to retrieve active MT5 orders",
    ):
        active_orders.get_active_order_count("XAUUSD")


def test_successful_empty_query_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        active_orders.mt5,
        "orders_get",
        lambda **kwargs: (),
    )

    assert active_orders.get_active_order_count("XAUUSD") == 0
