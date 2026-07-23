from __future__ import annotations

from types import SimpleNamespace

import pytest

import core.mt5_execution.account as account_module
from core.mt5_execution.account import get_account_info


def test_get_account_info_maps_broker_fields_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        account_module.mt5,
        "account_info",
        lambda: SimpleNamespace(
            login=12345678,
            server="Broker-Demo",
            balance=10_000.0,
            equity=9_950.0,
            margin=250.0,
            margin_free=9_700.0,
            leverage=500,
            currency="USD",
        ),
    )

    account = get_account_info()

    assert account.login == 12345678
    assert account.server == "Broker-Demo"
    assert account.balance == pytest.approx(10_000.0)
    assert account.equity == pytest.approx(9_950.0)
    assert account.margin == pytest.approx(250.0)
    assert account.free_margin == pytest.approx(9_700.0)
    assert account.leverage == 500
    assert account.currency == "USD"


def test_get_account_info_fails_closed_offline(
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
        get_account_info()
