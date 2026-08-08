from __future__ import annotations

import ast
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.mt5_connector as legacy_mt5
from core.mt5_connector import (
    LegacyBrokerMutationQuarantinedError,
    MT5Connector,
)

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.py"
_LEGACY_ENVIRONMENT_VARIABLES = (
    "XAUUSD_LEGACY_MT5_LOGIN",
    "XAUUSD_LEGACY_MT5_PASSWORD",
    "XAUUSD_LEGACY_MT5_SERVER",
)


def _load_legacy_config(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    for name in _LEGACY_ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    return runpy.run_path(str(_CONFIG_PATH))


def test_legacy_config_has_no_committed_mt5_credential_literals() -> None:
    tree = ast.parse(_CONFIG_PATH.read_text(encoding="utf-8"))
    credential_assignments = {
        target.id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
        and target.id in {"MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER"}
    }

    assert set(credential_assignments) == {
        "MT5_LOGIN",
        "MT5_PASSWORD",
        "MT5_SERVER",
    }
    assert all(
        isinstance(value, ast.Call) for value in credential_assignments.values()
    )


def test_legacy_config_defaults_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _load_legacy_config(monkeypatch)

    assert config["MT5_LOGIN"] == 0
    assert config["MT5_PASSWORD"] == ""
    assert config["MT5_SERVER"] == ""
    assert config["LIVE_TRADING"] is False
    assert config["TRAILING_STOP_ENABLED"] is False


def test_legacy_environment_reads_remain_available_for_quarantined_compatibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XAUUSD_LEGACY_MT5_LOGIN", "42")
    monkeypatch.setenv("XAUUSD_LEGACY_MT5_PASSWORD", "test-only")
    monkeypatch.setenv("XAUUSD_LEGACY_MT5_SERVER", "legacy-demo.invalid")

    config = runpy.run_path(str(_CONFIG_PATH))

    assert config["MT5_LOGIN"] == 42
    assert config["MT5_PASSWORD"] == "test-only"
    assert config["MT5_SERVER"] == "legacy-demo.invalid"
    assert config["LIVE_TRADING"] is False
    assert config["TRAILING_STOP_ENABLED"] is False


@pytest.fixture
def connected_legacy_connector(
    monkeypatch: pytest.MonkeyPatch,
) -> MT5Connector:
    def unexpected_order_send(_request: object) -> None:
        pytest.fail("legacy quarantine allowed mt5.order_send")

    monkeypatch.setattr(legacy_mt5, "MT5_AVAILABLE", True)
    monkeypatch.setattr(
        legacy_mt5,
        "mt5",
        SimpleNamespace(order_send=unexpected_order_send),
        raising=False,
    )
    connector = MT5Connector(login=0, password="", server="")
    connector.connected = True
    return connector


def test_connected_legacy_place_order_fails_before_order_send(
    connected_legacy_connector: MT5Connector,
) -> None:
    with pytest.raises(
        LegacyBrokerMutationQuarantinedError,
        match="order placement is quarantined",
    ):
        connected_legacy_connector.place_order(
            symbol="XAUUSD",
            action="BUY",
            lot=0.01,
            sl=2290.0,
            tp=2320.0,
            magic=1,
        )


def test_connected_legacy_modify_sl_fails_before_order_send(
    connected_legacy_connector: MT5Connector,
) -> None:
    with pytest.raises(
        LegacyBrokerMutationQuarantinedError,
        match="stop-loss modification is quarantined",
    ):
        connected_legacy_connector.modify_sl(
            ticket=1,
            symbol="XAUUSD",
            new_sl=2300.0,
            tp=2320.0,
        )


def test_disconnected_legacy_mutations_remain_simulated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(legacy_mt5, "MT5_AVAILABLE", True)
    connector = MT5Connector(login=0, password="", server="")

    order_result = connector.place_order(
        symbol="XAUUSD",
        action="BUY",
        lot=0.01,
        sl=2290.0,
        tp=2320.0,
        magic=1,
    )
    modify_result = connector.modify_sl(
        ticket=order_result["order"],
        symbol="XAUUSD",
        new_sl=2300.0,
        tp=2320.0,
    )

    assert order_result["simulated"] is True
    assert modify_result == {"retcode": 0, "simulated": True}
    assert connector.get_open_trade_count(symbol="XAUUSD", magic=1) == 1
