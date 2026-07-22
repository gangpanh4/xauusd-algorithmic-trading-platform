from __future__ import annotations

from types import SimpleNamespace

import pytest

import core.mt5_execution.account as account_module


def test_account_query_failure_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        account_module.mt5,
        "account_info",
        lambda: None,
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to retrieve MT5 account information",
    ):
        account_module.get_account_info()


def test_account_query_preserves_authoritative_broker_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        account_module.mt5,
        "account_info",
        lambda: SimpleNamespace(
            login=12345678,
            server="Broker-Demo",
            balance=10_000.0,
            equity=9_975.5,
            margin=150.0,
            margin_free=9_825.5,
            leverage=500,
            currency="USD",
        ),
    )

    account = account_module.get_account_info()

    assert account.login == 12345678
    assert account.server == "Broker-Demo"
    assert account.balance == pytest.approx(10_000.0)
    assert account.equity == pytest.approx(9_975.5)
    assert account.margin == pytest.approx(150.0)
    assert account.free_margin == pytest.approx(9_825.5)
    assert account.leverage == 500
    assert account.currency == "USD"


def test_account_query_does_not_replace_equity_with_balance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        account_module.mt5,
        "account_info",
        lambda: SimpleNamespace(
            login=1,
            server="Demo",
            balance=5_000.0,
            equity=4_800.0,
            margin=100.0,
            margin_free=4_700.0,
            leverage=100,
            currency="USD",
        ),
    )

    account = account_module.get_account_info()

    assert account.balance == pytest.approx(5_000.0)
    assert account.equity == pytest.approx(4_800.0)
    assert account.balance != account.equity
