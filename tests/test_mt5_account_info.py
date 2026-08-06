from __future__ import annotations

from types import SimpleNamespace

from core.mt5_execution.account import get_account_info


def test_get_account_info_preserves_trade_mode(monkeypatch) -> None:
    account = SimpleNamespace(
        login=123456,
        server="Broker-Demo",
        balance=10_000.0,
        equity=10_000.0,
        margin=0.0,
        margin_free=10_000.0,
        leverage=100,
        currency="USD",
        trade_mode=0,
    )
    monkeypatch.setattr(
        "core.mt5_execution.account.mt5.account_info",
        lambda: account,
    )

    result = get_account_info()

    assert result.trade_mode == 0
    assert result.login == 123456
    assert result.server == "Broker-Demo"
