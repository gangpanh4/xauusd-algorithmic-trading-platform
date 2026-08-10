from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import core.live_trading.demo_execution_authorization as authorization_module
import core.live_trading.demo_execution_authorization_prepare as prepare_module
from core.live_trading.config import LiveTradingConfig
from core.live_trading.demo_execution_authorization import (
    DemoExecutionAuthorizationError,
    create_fresh_demo_execution_authorization,
    load_demo_execution_authorization,
)
from core.live_trading.execution_concurrency import (
    LocalExecutionLock,
    build_execution_lock_path,
)
from core.live_trading.execution_intent_store import (
    ExecutionIntentStatus,
    ExecutionIntentStore,
    PersistedExecutionIntent,
)
from core.live_trading.partial_fill_store import (
    PartialFillStateStore,
    PersistedPartialFill,
)

NOW = datetime(2026, 8, 10, 8, 0, tzinfo=UTC)
ACK = "I AUTHORIZE ONE DEMO ORDER"


def _config(tmp_path: Path) -> LiveTradingConfig:
    return LiveTradingConfig(
        demo_authorization_path=tmp_path / "demo_execution_authorization.json",
        execution_intent_state_path=tmp_path / "live_execution_intent.json",
        partial_fill_state_path=tmp_path / "live_partial_fill_state.json",
        demo_authorization_max_lifetime_seconds=900,
    )


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "authorization_id": "old-demo-canary",
        "issued_at": (NOW - timedelta(minutes=10)).isoformat(),
        "expires_at": (NOW - timedelta(minutes=1)).isoformat(),
        "account_login": 123456,
        "account_server": "MetaQuotes-Demo",
        "symbol": "XAUUSD",
        "maximum_volume": 0.01,
        "maximum_submissions": 1,
        "demo_only": True,
        "one_shot": True,
        "acknowledgement": ACK,
        "consumed_at": None,
        "consumed_intent_key": None,
    }
    payload.update(overrides)
    return payload


def _write_authorization(path: Path, **overrides: object) -> bytes:
    data = json.dumps(
        _payload(**overrides),
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    path.write_bytes(data)
    return data


def _create(config: LiveTradingConfig):
    return create_fresh_demo_execution_authorization(
        config=config,
        account_login=123456,
        account_server="MetaQuotes-Demo",
        account_trade_mode=0,
        demo_account_confirmed=True,
        acknowledgement=ACK,
        now=NOW,
    )


def _archive_path(config: LiveTradingConfig) -> Path:
    return (
        config.demo_authorization_path.parent
        / "archive"
        / "demo_execution_authorizations"
        / "old-demo-canary.json"
    )


def _intent(status: ExecutionIntentStatus) -> PersistedExecutionIntent:
    return PersistedExecutionIntent(
        intent_key="a" * 64,
        symbol="XAUUSD",
        observation_timestamp=NOW - timedelta(minutes=5),
        side="BUY",
        volume=0.01,
        entry_price=2400.0,
        stop_loss=2390.0,
        take_profit=2420.0,
        status=status,
        ticket=None,
        created_at=NOW - timedelta(minutes=4),
        updated_at=NOW - timedelta(minutes=4),
        magic_number=0,
        broker_comment="xau:" + ("a" * 16),
    )


def test_no_existing_file_creates_fresh_authorization(tmp_path: Path) -> None:
    config = _config(tmp_path)

    result = _create(config)

    loaded = load_demo_execution_authorization(config.demo_authorization_path)
    assert result.rotated_expired_authorization is False
    assert result.archived_authorization_path is None
    assert loaded == result.authorization
    assert loaded.consumed is False


def test_valid_active_unconsumed_authorization_rejects_replacement(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    original = _write_authorization(
        config.demo_authorization_path,
        issued_at=(NOW - timedelta(minutes=1)).isoformat(),
        expires_at=(NOW + timedelta(minutes=4)).isoformat(),
    )

    with pytest.raises(
        DemoExecutionAuthorizationError,
        match="valid unconsumed authorization cannot be replaced",
    ):
        _create(config)

    assert config.demo_authorization_path.read_bytes() == original
    assert _archive_path(config).exists() is False


def test_expired_unconsumed_is_archived_exactly_then_replaced(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    original = _write_authorization(config.demo_authorization_path)

    result = _create(config)

    assert result.rotated_expired_authorization is True
    assert result.archived_authorization_path == _archive_path(config)
    assert _archive_path(config).read_bytes() == original
    fresh = load_demo_execution_authorization(config.demo_authorization_path)
    assert fresh.authorization_id != "old-demo-canary"
    assert fresh.consumed is False


def test_identical_existing_archive_is_idempotently_acceptable(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    original = _write_authorization(config.demo_authorization_path)
    archive = _archive_path(config)
    archive.parent.mkdir(parents=True)
    archive.write_bytes(original)

    _create(config)

    assert archive.read_bytes() == original
    assert (
        load_demo_execution_authorization(
            config.demo_authorization_path
        ).authorization_id
        != "old-demo-canary"
    )


def test_conflicting_archive_fails_closed_without_active_replacement(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    original = _write_authorization(config.demo_authorization_path)
    archive = _archive_path(config)
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"different")

    with pytest.raises(
        DemoExecutionAuthorizationError,
        match="collision contains different content",
    ):
        _create(config)

    assert config.demo_authorization_path.read_bytes() == original
    assert archive.read_bytes() == b"different"


def test_consumed_authorization_is_preserved_and_rejected(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    original = _write_authorization(
        config.demo_authorization_path,
        consumed_at=(NOW - timedelta(minutes=2)).isoformat(),
        consumed_intent_key="b" * 64,
    )

    with pytest.raises(
        DemoExecutionAuthorizationError,
        match="Consumed demo authorization cannot be automatically rotated",
    ):
        _create(config)

    assert config.demo_authorization_path.read_bytes() == original
    assert _archive_path(config).exists() is False


def test_consumed_intent_key_alone_is_treated_as_consumed(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    original = _write_authorization(
        config.demo_authorization_path,
        consumed_intent_key="b" * 64,
    )

    with pytest.raises(
        DemoExecutionAuthorizationError,
        match="Consumed demo authorization cannot be automatically rotated",
    ):
        _create(config)

    assert config.demo_authorization_path.read_bytes() == original


def test_malformed_authorization_fails_closed(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.demo_authorization_path.write_bytes(b"{not-json")

    with pytest.raises(DemoExecutionAuthorizationError):
        _create(config)

    assert config.demo_authorization_path.read_bytes() == b"{not-json"


def test_authorization_lock_conflict_fails_closed(tmp_path: Path) -> None:
    config = _config(tmp_path)
    original = _write_authorization(config.demo_authorization_path)
    lock = LocalExecutionLock(
        build_execution_lock_path(
            config.demo_authorization_path,
            scope="authorization-consumption",
        ),
        purpose="demo authorization consumption",
    )
    owner = lock.acquire()
    try:
        with pytest.raises(
            DemoExecutionAuthorizationError,
            match="lifecycle ownership is uncertain",
        ):
            _create(config)
        assert config.demo_authorization_path.read_bytes() == original
    finally:
        lock.release(owner)


@pytest.mark.parametrize(
    "status",
    [
        ExecutionIntentStatus.PREPARED,
        ExecutionIntentStatus.PENDING,
        ExecutionIntentStatus.PARTIALLY_FILLED,
    ],
)
def test_unresolved_execution_intent_blocks_rotation(
    tmp_path: Path,
    status: ExecutionIntentStatus,
) -> None:
    config = _config(tmp_path)
    original = _write_authorization(config.demo_authorization_path)
    ExecutionIntentStore(config.execution_intent_state_path).save(
        _intent(status)
    )

    with pytest.raises(
        DemoExecutionAuthorizationError,
        match="unresolved execution intent",
    ):
        _create(config)

    assert config.demo_authorization_path.read_bytes() == original


def test_unresolved_partial_fill_blocks_rotation(tmp_path: Path) -> None:
    config = _config(tmp_path)
    original = _write_authorization(config.demo_authorization_path)
    PartialFillStateStore(config.partial_fill_state_path).save(
        PersistedPartialFill(
            symbol="XAUUSD",
            ticket=99,
            requested_volume=0.01,
            executed_volume=0.004,
            remaining_volume=0.006,
            created_at=NOW,
        )
    )

    with pytest.raises(
        DemoExecutionAuthorizationError,
        match="unresolved partial fill",
    ):
        _create(config)

    assert config.demo_authorization_path.read_bytes() == original


@pytest.mark.parametrize(
    "overrides",
    [
        {"account_login": 999999},
        {"account_server": "Other-Demo"},
        {"symbol": "EURUSD"},
    ],
)
def test_existing_binding_mismatch_fails_closed(
    tmp_path: Path,
    overrides: dict[str, object],
) -> None:
    config = _config(tmp_path)
    original = _write_authorization(
        config.demo_authorization_path,
        **overrides,
    )

    with pytest.raises(
        DemoExecutionAuthorizationError,
        match="binding does not match",
    ):
        _create(config)

    assert config.demo_authorization_path.read_bytes() == original


def test_fresh_authorization_scope_is_exact_one_shot_xauusd(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)

    fresh = _create(config).authorization

    assert fresh.demo_only is True
    assert fresh.one_shot is True
    assert fresh.symbol == "XAUUSD"
    assert fresh.maximum_volume == pytest.approx(0.01)
    assert fresh.maximum_submissions == 1
    assert fresh.acknowledgement == ACK
    assert fresh.account_login == 123456
    assert fresh.account_server == "MetaQuotes-Demo"
    assert fresh.consumed_at is None
    assert fresh.consumed_intent_key is None
    assert fresh.consumed is False
    assert fresh.expires_at - fresh.issued_at == timedelta(seconds=900)


def test_rotation_never_consumes_old_or_fresh_authorization(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    _write_authorization(config.demo_authorization_path)

    fresh = _create(config).authorization
    archived = json.loads(_archive_path(config).read_text(encoding="utf-8"))

    assert archived["consumed_at"] is None
    assert archived["consumed_intent_key"] is None
    assert fresh.consumed is False


def test_archive_durability_failure_prevents_active_replacement(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    original = _write_authorization(config.demo_authorization_path)
    real_fsync = authorization_module._fsync_directory

    def fail_archive_directory(directory: Path) -> None:
        if directory.name == "demo_execution_authorizations":
            raise OSError("injected archive fsync failure")
        real_fsync(directory)

    monkeypatch.setattr(
        authorization_module,
        "_fsync_directory",
        fail_archive_directory,
    )

    with pytest.raises(
        DemoExecutionAuthorizationError,
        match="durably archive",
    ):
        _create(config)

    assert config.demo_authorization_path.read_bytes() == original
    assert _archive_path(config).read_bytes() == original


def test_directory_fsync_supports_runtime_filesystem(tmp_path: Path) -> None:
    authorization_module._fsync_directory(tmp_path)


def _preflight_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "recorded_at": (NOW - timedelta(minutes=1)).isoformat(),
        "symbol": "XAUUSD",
        "account_login": 123456,
        "account_server": "MetaQuotes-Demo",
        "account_trade_mode": 0,
        "demo_account_confirmed": True,
        "symbol_specification_loaded": True,
        "symbol_trade_allowed": True,
        "symbol_volume_min": 0.01,
        "symbol_volume_max": 100.0,
        "symbol_volume_step": 0.01,
        "symbol_tick_size": 0.01,
        "symbol_minimum_stop_distance": 0.01,
        "active_order_count": 0,
        "historical_order_count": 1,
        "execution_deal_count": 1,
        "open_position_count": 0,
        "persisted_intent_present": False,
        "persisted_intent_status": None,
        "reconciliation_disposition": "NO_PERSISTED_INTENT",
        "reconciliation_clear": True,
        "unresolved_partial_fill": False,
        "unresolved_partial_ticket": None,
        "live_execution_enabled": False,
        "demo_execution_approved": False,
        "execution_kill_switch_enabled": True,
        "order_submission_attempted": False,
        "authorization_consumed": False,
        "trade_executed": False,
        "validation_passed": True,
        "reasons": [],
    }
    payload.update(overrides)
    return payload


def test_production_preparation_uses_fresh_connected_preflight_binding(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    preflight = tmp_path / "preflight.json"
    preflight.write_text(
        json.dumps(_preflight_payload()),
        encoding="utf-8",
    )

    result = prepare_module.prepare_fresh_demo_authorization_from_preflight(
        config=config,
        preflight_path=preflight,
        acknowledgement=ACK,
        now=NOW,
    )

    assert result.authorization.account_login == 123456
    assert result.authorization.account_server == "MetaQuotes-Demo"
    assert result.authorization.symbol == "XAUUSD"


def test_stale_connected_preflight_is_rejected(tmp_path: Path) -> None:
    config = _config(tmp_path)
    preflight = tmp_path / "preflight.json"
    preflight.write_text(
        json.dumps(
            _preflight_payload(
                recorded_at=(NOW - timedelta(minutes=16)).isoformat()
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        prepare_module.DemoAuthorizationPreparationError,
        match="older than 15 minutes",
    ):
        prepare_module.prepare_fresh_demo_authorization_from_preflight(
            config=config,
            preflight_path=preflight,
            acknowledgement=ACK,
            now=NOW,
        )


def test_preparation_module_has_no_broker_mutation_surface() -> None:
    source = inspect.getsource(prepare_module)

    assert "MetaTrader5" not in source
    assert "order_check" not in source
    assert "order_send" not in source
    assert "consume_demo_execution_authorization" not in source
    assert "--force" not in source
    assert "--overwrite" not in source
    assert "--ignore-consumed" not in source
    assert "--ignore-intent" not in source
    assert "--skip-archive" not in source
