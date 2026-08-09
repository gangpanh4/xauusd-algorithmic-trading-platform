from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta

import pytest

from core.live_trading.config import LiveTradingConfig
from core.live_trading.demo_execution_authorization import (
    DemoExecutionAuthorizationError,
    consume_demo_execution_authorization,
    load_demo_execution_authorization,
    validate_demo_execution_authorization,
)
from core.live_trading.execution_concurrency import (
    LocalExecutionLock,
    build_execution_lock_path,
)
from core.mt5_execution.models import AccountInfo, OrderRequest, OrderSide

NOW = datetime(2026, 8, 8, 1, 15, tzinfo=UTC)


def _config(tmp_path) -> LiveTradingConfig:
    return LiveTradingConfig(
        live_execution_enabled=True,
        demo_execution_approved=True,
        execution_kill_switch_enabled=False,
        approved_account_login=123456,
        approved_account_server="MetaQuotes-Demo",
        demo_authorization_path=tmp_path / "authorization.json",
        demo_authorization_max_lifetime_seconds=900,
    )


def _account() -> AccountInfo:
    return AccountInfo(
        login=123456,
        server="MetaQuotes-Demo",
        balance=10000.0,
        equity=10000.0,
        margin=0.0,
        free_margin=10000.0,
        leverage=100,
        currency="USD",
        trade_mode=0,
    )


def _request(volume: float = 0.01) -> OrderRequest:
    return OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=volume,
        entry_price=2400.0,
        stop_loss=2390.0,
        take_profit=2420.0,
    )


def _write(path, **overrides) -> None:
    payload = {
        "schema_version": 1,
        "authorization_id": "demo-canary-001",
        "issued_at": (NOW - timedelta(minutes=1)).isoformat(),
        "expires_at": (NOW + timedelta(minutes=4)).isoformat(),
        "account_login": 123456,
        "account_server": "MetaQuotes-Demo",
        "symbol": "XAUUSD",
        "maximum_volume": 0.01,
        "maximum_submissions": 1,
        "demo_only": True,
        "one_shot": True,
        "acknowledgement": "I AUTHORIZE ONE DEMO ORDER",
        "consumed_at": None,
        "consumed_intent_key": None,
    }
    payload.update(overrides)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_valid_authorization_passes_and_consumes_once(tmp_path) -> None:
    config = _config(tmp_path)
    _write(config.demo_authorization_path)
    authorization = load_demo_execution_authorization(
        config.demo_authorization_path
    )
    validate_demo_execution_authorization(
        authorization,
        config=config,
        account=_account(),
        request=_request(),
        now=NOW,
    )
    consume_demo_execution_authorization(
        config.demo_authorization_path,
        authorization,
        intent_key="a" * 64,
        consumed_at=NOW,
    )
    loaded = load_demo_execution_authorization(config.demo_authorization_path)
    assert loaded.consumed_intent_key == "a" * 64
    with pytest.raises(DemoExecutionAuthorizationError, match="already been consumed"):
        validate_demo_execution_authorization(
            loaded,
            config=config,
            account=_account(),
            request=_request(),
            now=NOW,
        )


def test_two_stale_authorization_contenders_exactly_one_consumes(
    tmp_path,
) -> None:
    config = _config(tmp_path)
    _write(config.demo_authorization_path)
    authorizations = [
        load_demo_execution_authorization(config.demo_authorization_path),
        load_demo_execution_authorization(config.demo_authorization_path),
    ]
    intent_keys = ["a" * 64, "b" * 64]
    barrier = threading.Barrier(2)
    successes: list[str] = []
    failures: list[DemoExecutionAuthorizationError] = []

    def contend(index: int) -> None:
        barrier.wait()
        try:
            consume_demo_execution_authorization(
                config.demo_authorization_path,
                authorizations[index],
                intent_key=intent_keys[index],
                consumed_at=NOW,
            )
        except DemoExecutionAuthorizationError as exc:
            failures.append(exc)
        else:
            successes.append(intent_keys[index])

    threads = [threading.Thread(target=contend, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(successes) == 1
    assert len(failures) == 1
    assert load_demo_execution_authorization(
        config.demo_authorization_path
    ).consumed_intent_key == successes[0]


def test_crashed_authorization_owner_blocks_restart(tmp_path) -> None:
    config = _config(tmp_path)
    _write(config.demo_authorization_path)
    authorization = load_demo_execution_authorization(
        config.demo_authorization_path
    )
    lock = LocalExecutionLock(
        build_execution_lock_path(
            config.demo_authorization_path,
            scope="authorization-consumption",
        ),
        purpose="demo authorization consumption",
    )
    lock.acquire()

    with pytest.raises(
        DemoExecutionAuthorizationError,
        match="ownership is uncertain",
    ):
        consume_demo_execution_authorization(
            config.demo_authorization_path,
            authorization,
            intent_key="a" * 64,
            consumed_at=NOW,
        )
    assert config.demo_authorization_path.is_file()


def test_authorization_rejects_real_account(tmp_path) -> None:
    config = _config(tmp_path)
    _write(config.demo_authorization_path)
    account = AccountInfo(
        login=123456,
        server="MetaQuotes-Demo",
        balance=10000.0,
        equity=10000.0,
        margin=0.0,
        free_margin=10000.0,
        leverage=100,
        currency="USD",
        trade_mode=2,
    )
    with pytest.raises(
        DemoExecutionAuthorizationError,
        match="restricted to an MT5 demo account",
    ):
        validate_demo_execution_authorization(
            load_demo_execution_authorization(config.demo_authorization_path),
            config=config,
            account=account,
            request=_request(),
            now=NOW,
        )


def test_authorization_rejects_expired_permission(tmp_path) -> None:
    config = _config(tmp_path)
    _write(
        config.demo_authorization_path,
        issued_at=(NOW - timedelta(minutes=10)).isoformat(),
        expires_at=(NOW - timedelta(minutes=1)).isoformat(),
    )
    with pytest.raises(DemoExecutionAuthorizationError, match="expired"):
        validate_demo_execution_authorization(
            load_demo_execution_authorization(config.demo_authorization_path),
            config=config,
            account=_account(),
            request=_request(),
            now=NOW,
        )


def test_authorization_rejects_excess_volume(tmp_path) -> None:
    config = _config(tmp_path)
    _write(config.demo_authorization_path)
    with pytest.raises(
        DemoExecutionAuthorizationError,
        match="exceeds the authorized volume",
    ):
        validate_demo_execution_authorization(
            load_demo_execution_authorization(config.demo_authorization_path),
            config=config,
            account=_account(),
            request=_request(volume=0.02),
            now=NOW,
        )


def test_authorization_requires_kill_switch_clear(tmp_path) -> None:
    config = LiveTradingConfig(
        live_execution_enabled=True,
        demo_execution_approved=True,
        execution_kill_switch_enabled=True,
        approved_account_login=123456,
        approved_account_server="MetaQuotes-Demo",
        demo_authorization_path=tmp_path / "authorization.json",
    )
    _write(config.demo_authorization_path)
    with pytest.raises(DemoExecutionAuthorizationError, match="kill switch"):
        validate_demo_execution_authorization(
            load_demo_execution_authorization(config.demo_authorization_path),
            config=config,
            account=_account(),
            request=_request(),
            now=NOW,
        )
