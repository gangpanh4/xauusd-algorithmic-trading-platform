from __future__ import annotations

from types import SimpleNamespace

import pytest

import core.platform.engine as platform_module


def test_platform_uses_centralized_account_helper() -> None:
    assert platform_module.get_account_info is not platform_module.mt5.account_info


def test_centralized_account_failure_remains_fail_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        platform_module,
        "get_account_info",
        lambda: (_ for _ in ()).throw(
            RuntimeError("Unable to retrieve MT5 account information.")
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to retrieve MT5 account information",
    ):
        platform_module.get_account_info()


def test_centralized_account_object_exposes_balance_for_risk_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = SimpleNamespace(balance=10_000.0)
    monkeypatch.setattr(
        platform_module,
        "get_account_info",
        lambda: expected,
    )

    account = platform_module.get_account_info()

    assert account is expected
    assert account.balance == pytest.approx(10_000.0)
