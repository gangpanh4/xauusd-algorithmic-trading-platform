"""Fail-closed one-shot authorization for MT5 demo order submission."""

from __future__ import annotations

import ctypes
import json
import os
import tempfile
from ctypes import wintypes
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from math import isclose, isfinite
from pathlib import Path
from typing import Any, Final
from uuid import uuid4

from core.mt5_execution.models import AccountInfo, OrderRequest

from .config import LiveTradingConfig
from .execution_concurrency import (
    ExecutionConcurrencyError,
    LocalExecutionLock,
    build_execution_lock_path,
)
from .execution_intent_store import (
    ExecutionIntentStateError,
    ExecutionIntentStore,
)
from .partial_fill_store import PartialFillStateError, PartialFillStateStore

_SCHEMA_VERSION: Final = 1
_DEMO_TRADE_MODE: Final = 0
_REQUIRED_ACKNOWLEDGEMENT: Final = "I AUTHORIZE ONE DEMO ORDER"
_CANARY_SYMBOL: Final = "XAUUSD"
_CANARY_VOLUME: Final = 0.01
_VOLUME_TOLERANCE: Final = 1e-12
_FRESH_AUTHORIZATION_TTL_SECONDS: Final = 900


class DemoExecutionAuthorizationError(RuntimeError):
    """Raised when explicit demo execution authorization is absent or invalid."""


@dataclass(frozen=True, slots=True)
class DemoExecutionAuthorization:
    schema_version: int
    authorization_id: str
    issued_at: datetime
    expires_at: datetime
    account_login: int
    account_server: str
    symbol: str
    maximum_volume: float
    maximum_submissions: int
    demo_only: bool
    one_shot: bool
    acknowledgement: str
    consumed_at: datetime | None = None
    consumed_intent_key: str | None = None

    @property
    def consumed(self) -> bool:
        return self.consumed_at is not None or self.consumed_intent_key is not None

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["issued_at"] = _aware_utc(self.issued_at, "issued_at").isoformat()
        payload["expires_at"] = _aware_utc(self.expires_at, "expires_at").isoformat()
        payload["consumed_at"] = (
            None
            if self.consumed_at is None
            else _aware_utc(self.consumed_at, "consumed_at").isoformat()
        )
        return payload


def load_demo_execution_authorization(
    path: str | Path,
) -> DemoExecutionAuthorization:
    source = Path(path)
    lock = _authorization_consumption_lock(source)
    try:
        lock.assert_clear()
        authorization = _load_demo_execution_authorization_unlocked(source)
        lock.assert_clear()
    except ExecutionConcurrencyError as exc:
        raise DemoExecutionAuthorizationError(
            "Demo execution authorization ownership is uncertain."
        ) from exc
    return authorization


def _load_demo_execution_authorization_unlocked(
    path: str | Path,
) -> DemoExecutionAuthorization:
    source = Path(path)
    if not source.is_file():
        raise DemoExecutionAuthorizationError(
            f"Demo execution authorization file does not exist: {source}"
        )
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DemoExecutionAuthorizationError(
            "Demo execution authorization could not be read."
        ) from exc
    if not isinstance(payload, dict):
        raise DemoExecutionAuthorizationError(
            "Demo execution authorization must be a JSON object."
        )
    expected = {
        "schema_version",
        "authorization_id",
        "issued_at",
        "expires_at",
        "account_login",
        "account_server",
        "symbol",
        "maximum_volume",
        "maximum_submissions",
        "demo_only",
        "one_shot",
        "acknowledgement",
        "consumed_at",
        "consumed_intent_key",
    }
    if set(payload) != expected:
        raise DemoExecutionAuthorizationError(
            "Demo execution authorization schema is invalid."
        )
    try:
        authorization = DemoExecutionAuthorization(
            schema_version=_strict_int(payload["schema_version"], "schema_version"),
            authorization_id=str(payload["authorization_id"]),
            issued_at=_parse_datetime(payload["issued_at"], "issued_at"),
            expires_at=_parse_datetime(payload["expires_at"], "expires_at"),
            account_login=_strict_int(payload["account_login"], "account_login"),
            account_server=str(payload["account_server"]),
            symbol=str(payload["symbol"]),
            maximum_volume=float(payload["maximum_volume"]),
            maximum_submissions=_strict_int(
                payload["maximum_submissions"], "maximum_submissions"
            ),
            demo_only=_strict_bool(payload["demo_only"], "demo_only"),
            one_shot=_strict_bool(payload["one_shot"], "one_shot"),
            acknowledgement=str(payload["acknowledgement"]),
            consumed_at=(
                None
                if payload["consumed_at"] is None
                else _parse_datetime(payload["consumed_at"], "consumed_at")
            ),
            consumed_intent_key=(
                None
                if payload["consumed_intent_key"] is None
                else str(payload["consumed_intent_key"])
            ),
        )
    except (TypeError, ValueError) as exc:
        raise DemoExecutionAuthorizationError(
            "Demo execution authorization contains invalid field values."
        ) from exc
    return authorization


def validate_demo_execution_authorization_time_window(
    authorization: DemoExecutionAuthorization,
    *,
    now: datetime,
) -> None:
    """Validate only the authoritative authorization activation window."""

    observed_at = _aware_utc(now, "now")
    issued_at = _aware_utc(authorization.issued_at, "authorization.issued_at")
    expires_at = _aware_utc(
        authorization.expires_at,
        "authorization.expires_at",
    )
    if observed_at < issued_at:
        raise DemoExecutionAuthorizationError(
            "Demo authorization is not active yet."
        )
    if observed_at > expires_at:
        raise DemoExecutionAuthorizationError(
            "Demo authorization has expired."
        )


def validate_demo_execution_authorization_scope(
    authorization: DemoExecutionAuthorization,
    *,
    config: LiveTradingConfig,
    account: AccountInfo,
    now: datetime,
) -> None:
    """Validate authorization/account/control scope without inventing a request."""

    observed_at = _aware_utc(now, "now")
    if authorization.schema_version != _SCHEMA_VERSION:
        raise DemoExecutionAuthorizationError(
            "Unsupported demo authorization schema version."
        )
    if not authorization.authorization_id.strip():
        raise DemoExecutionAuthorizationError(
            "Demo authorization ID is empty."
        )
    if authorization.consumed:
        raise DemoExecutionAuthorizationError(
            "Demo execution authorization has already been consumed."
        )
    if not config.live_execution_enabled:
        raise DemoExecutionAuthorizationError("Live execution is disabled.")
    if not config.demo_execution_approved:
        raise DemoExecutionAuthorizationError(
            "Demo execution has not been explicitly approved."
        )
    if config.execution_kill_switch_enabled:
        raise DemoExecutionAuthorizationError(
            "Execution kill switch is enabled."
        )
    if account.trade_mode != _DEMO_TRADE_MODE or not authorization.demo_only:
        raise DemoExecutionAuthorizationError(
            "Execution authorization is restricted to an MT5 demo account."
        )
    if (
        config.approved_account_login is None
        or config.approved_account_server is None
        or account.login != config.approved_account_login
        or account.server != config.approved_account_server
        or authorization.account_login != account.login
        or authorization.account_server != account.server
    ):
        raise DemoExecutionAuthorizationError(
            "Connected account identity does not match explicit authorization."
        )
    if authorization.symbol != config.symbol:
        raise DemoExecutionAuthorizationError(
            "Authorized symbol does not match the execution request."
        )
    if authorization.maximum_submissions != 1 or not authorization.one_shot:
        raise DemoExecutionAuthorizationError(
            "Demo authorization must permit exactly one submission."
        )
    if authorization.acknowledgement != _REQUIRED_ACKNOWLEDGEMENT:
        raise DemoExecutionAuthorizationError(
            "Demo authorization acknowledgement is invalid."
        )
    lifetime = (
        _aware_utc(
            authorization.expires_at,
            "authorization.expires_at",
        )
        - _aware_utc(
            authorization.issued_at,
            "authorization.issued_at",
        )
    ).total_seconds()
    configured_lifetime = config.demo_authorization_max_lifetime_seconds
    if (
        isinstance(configured_lifetime, bool)
        or not isinstance(configured_lifetime, int)
        or configured_lifetime <= 0
        or lifetime <= 0
        or lifetime > configured_lifetime
    ):
        raise DemoExecutionAuthorizationError(
            "Demo authorization lifetime is invalid."
        )
    validate_demo_execution_authorization_time_window(
        authorization,
        now=observed_at,
    )


def validate_demo_execution_authorization(
    authorization: DemoExecutionAuthorization,
    *,
    config: LiveTradingConfig,
    account: AccountInfo,
    request: OrderRequest,
    now: datetime,
) -> None:
    validate_demo_execution_authorization_scope(
        authorization,
        config=config,
        account=account,
        now=now,
    )
    if request.symbol != config.symbol:
        raise DemoExecutionAuthorizationError(
            "Authorized symbol does not match the execution request."
        )
    maximum_volume = authorization.maximum_volume
    request_volume = float(request.volume)
    if (
        not isfinite(maximum_volume)
        or not isfinite(request_volume)
        or maximum_volume <= 0.0
        or request_volume <= 0.0
        or request_volume > maximum_volume
    ):
        raise DemoExecutionAuthorizationError(
            "Execution request exceeds the authorized volume."
        )


@dataclass(frozen=True, slots=True)
class DemoAuthorizationPreparationResult:
    """Result of one fail-closed fresh authorization preparation."""

    authorization: DemoExecutionAuthorization
    archived_authorization_path: Path | None
    rotated_expired_authorization: bool


def create_fresh_demo_execution_authorization(
    *,
    config: LiveTradingConfig,
    account_login: int,
    account_server: str,
    account_trade_mode: int,
    demo_account_confirmed: bool,
    acknowledgement: str,
    now: datetime,
) -> DemoAuthorizationPreparationResult:
    """Create or safely rotate the single authoritative demo authorization."""

    observed_at = _aware_utc(now, "now")
    _validate_fresh_authorization_request(
        config=config,
        account_login=account_login,
        account_server=account_server,
        account_trade_mode=account_trade_mode,
        demo_account_confirmed=demo_account_confirmed,
        acknowledgement=acknowledgement,
    )

    target = Path(config.demo_authorization_path)
    archive_directory = (
        target.parent / "archive" / "demo_execution_authorizations"
    )
    intent_store = ExecutionIntentStore(config.execution_intent_state_path)
    partial_fill_store = PartialFillStateStore(config.partial_fill_state_path)

    try:
        with _authorization_consumption_lock(target).hold():
            existing: DemoExecutionAuthorization | None = None
            existing_bytes: bytes | None = None
            if os.path.lexists(target):
                if target.is_symlink() or not target.is_file():
                    raise DemoExecutionAuthorizationError(
                        "Existing demo execution authorization path is not a "
                        "regular file."
                    )
                existing_bytes = _read_authorization_bytes(target)
                existing = _load_demo_execution_authorization_unlocked(target)
                reread = _read_authorization_bytes(target)
                if reread != existing_bytes:
                    raise DemoExecutionAuthorizationError(
                        "Demo execution authorization changed during retirement "
                        "validation."
                    )
                existing_bytes = reread

            _require_clear_retirement_state(
                intent_store=intent_store,
                partial_fill_store=partial_fill_store,
            )

            archived_path: Path | None = None
            rotated = False
            if existing is not None:
                _validate_existing_authorization_for_rotation(
                    existing,
                    config=config,
                    account_login=account_login,
                    account_server=account_server,
                    now=observed_at,
                )
                if existing_bytes is None:
                    raise DemoExecutionAuthorizationError(
                        "Existing authorization bytes are unavailable."
                    )
                archived_path = _archive_expired_authorization_durably(
                    archive_directory=archive_directory,
                    authorization=existing,
                    exact_bytes=existing_bytes,
                )
                _require_clear_retirement_state(
                    intent_store=intent_store,
                    partial_fill_store=partial_fill_store,
                )
                current_bytes = _read_authorization_bytes(target)
                if current_bytes != existing_bytes:
                    raise DemoExecutionAuthorizationError(
                        "Demo execution authorization changed before replacement."
                    )
                rotated = True

            fresh = _build_fresh_authorization(
                config=config,
                account_login=account_login,
                account_server=account_server,
                acknowledgement=acknowledgement,
                now=observed_at,
            )
            _write_active_authorization_durably(
                target=target,
                authorization=fresh,
                replacing_existing=existing is not None,
            )
    except ExecutionConcurrencyError as exc:
        raise DemoExecutionAuthorizationError(
            "Demo execution authorization lifecycle ownership is uncertain."
        ) from exc

    return DemoAuthorizationPreparationResult(
        authorization=fresh,
        archived_authorization_path=archived_path,
        rotated_expired_authorization=rotated,
    )


def _validate_fresh_authorization_request(
    *,
    config: LiveTradingConfig,
    account_login: int,
    account_server: str,
    account_trade_mode: int,
    demo_account_confirmed: bool,
    acknowledgement: str,
) -> None:
    if config.symbol != _CANARY_SYMBOL:
        raise DemoExecutionAuthorizationError(
            "Fresh demo authorization is restricted to XAUUSD."
        )
    if (
        isinstance(account_login, bool)
        or not isinstance(account_login, int)
        or account_login <= 0
    ):
        raise DemoExecutionAuthorizationError(
            "Fresh demo authorization account login is invalid."
        )
    if (
        not isinstance(account_server, str)
        or not account_server
        or account_server != account_server.strip()
    ):
        raise DemoExecutionAuthorizationError(
            "Fresh demo authorization account server is invalid."
        )
    if account_trade_mode != _DEMO_TRADE_MODE or not demo_account_confirmed:
        raise DemoExecutionAuthorizationError(
            "Fresh authorization requires a confirmed MT5 demo account."
        )
    if acknowledgement != _REQUIRED_ACKNOWLEDGEMENT:
        raise DemoExecutionAuthorizationError(
            "Demo authorization acknowledgement is invalid."
        )
    lifetime = config.demo_authorization_max_lifetime_seconds
    if (
        isinstance(lifetime, bool)
        or not isinstance(lifetime, int)
        or lifetime <= 0
    ):
        raise DemoExecutionAuthorizationError(
            "Demo authorization lifetime is invalid."
        )


def _require_clear_retirement_state(
    *,
    intent_store: ExecutionIntentStore,
    partial_fill_store: PartialFillStateStore,
) -> None:
    try:
        intent = intent_store.load()
    except ExecutionIntentStateError as exc:
        raise DemoExecutionAuthorizationError(
            "Execution-intent state cannot be trusted for authorization rotation."
        ) from exc
    if intent is not None and intent.unresolved:
        raise DemoExecutionAuthorizationError(
            "An unresolved execution intent blocks authorization rotation."
        )
    try:
        partial_fill = partial_fill_store.load()
    except PartialFillStateError as exc:
        raise DemoExecutionAuthorizationError(
            "Partial-fill state cannot be trusted for authorization rotation."
        ) from exc
    if partial_fill is not None:
        raise DemoExecutionAuthorizationError(
            "An unresolved partial fill blocks authorization rotation."
        )


def _validate_existing_authorization_for_rotation(
    authorization: DemoExecutionAuthorization,
    *,
    config: LiveTradingConfig,
    account_login: int,
    account_server: str,
    now: datetime,
) -> None:
    if authorization.schema_version != _SCHEMA_VERSION:
        raise DemoExecutionAuthorizationError(
            "Existing demo authorization schema version is invalid."
        )
    _validated_archive_name(authorization.authorization_id)
    if authorization.consumed:
        raise DemoExecutionAuthorizationError(
            "Consumed demo authorization cannot be automatically rotated."
        )
    if (
        authorization.account_login != account_login
        or authorization.account_server != account_server
        or authorization.symbol != config.symbol
    ):
        raise DemoExecutionAuthorizationError(
            "Existing authorization binding does not match the fresh "
            "account/server/symbol request."
        )
    if not authorization.demo_only or not authorization.one_shot:
        raise DemoExecutionAuthorizationError(
            "Existing authorization is not a valid demo-only one-shot grant."
        )
    if authorization.maximum_submissions != 1:
        raise DemoExecutionAuthorizationError(
            "Existing authorization does not permit exactly one submission."
        )
    if (
        not isfinite(float(authorization.maximum_volume))
        or not isclose(
            float(authorization.maximum_volume),
            _CANARY_VOLUME,
            rel_tol=0.0,
            abs_tol=_VOLUME_TOLERANCE,
        )
    ):
        raise DemoExecutionAuthorizationError(
            "Existing authorization maximum volume is not exactly 0.01 lot."
        )
    if authorization.acknowledgement != _REQUIRED_ACKNOWLEDGEMENT:
        raise DemoExecutionAuthorizationError(
            "Existing demo authorization acknowledgement is invalid."
        )
    lifetime = (
        _aware_utc(
            authorization.expires_at,
            "authorization.expires_at",
        )
        - _aware_utc(
            authorization.issued_at,
            "authorization.issued_at",
        )
    ).total_seconds()
    if (
        lifetime <= 0.0
        or lifetime > config.demo_authorization_max_lifetime_seconds
    ):
        raise DemoExecutionAuthorizationError(
            "Existing demo authorization lifetime is invalid."
        )

    try:
        validate_demo_execution_authorization_time_window(
            authorization,
            now=now,
        )
    except DemoExecutionAuthorizationError as exc:
        if str(exc) != "Demo authorization has expired.":
            raise DemoExecutionAuthorizationError(
                "Existing authorization is not eligible for retirement."
            ) from exc
    else:
        raise DemoExecutionAuthorizationError(
            "A valid unconsumed authorization cannot be replaced."
        )


def _build_fresh_authorization(
    *,
    config: LiveTradingConfig,
    account_login: int,
    account_server: str,
    acknowledgement: str,
    now: datetime,
) -> DemoExecutionAuthorization:
    lifetime_seconds = min(
        config.demo_authorization_max_lifetime_seconds,
        _FRESH_AUTHORIZATION_TTL_SECONDS,
    )
    return DemoExecutionAuthorization(
        schema_version=_SCHEMA_VERSION,
        authorization_id=str(uuid4()),
        issued_at=now,
        expires_at=now + timedelta(seconds=lifetime_seconds),
        account_login=account_login,
        account_server=account_server,
        symbol=_CANARY_SYMBOL,
        maximum_volume=_CANARY_VOLUME,
        maximum_submissions=1,
        demo_only=True,
        one_shot=True,
        acknowledgement=acknowledgement,
        consumed_at=None,
        consumed_intent_key=None,
    )


def _archive_expired_authorization_durably(
    *,
    archive_directory: Path,
    authorization: DemoExecutionAuthorization,
    exact_bytes: bytes,
) -> Path:
    try:
        archive_directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DemoExecutionAuthorizationError(
            "Unable to create demo authorization archive directory."
        ) from exc

    archive_path = archive_directory / (
        f"{_validated_archive_name(authorization.authorization_id)}.json"
    )
    if os.path.lexists(archive_path):
        if archive_path.is_symlink() or not archive_path.is_file():
            raise DemoExecutionAuthorizationError(
                "Authorization archive collision is not a regular file."
            )
        if _read_authorization_bytes(archive_path) != exact_bytes:
            raise DemoExecutionAuthorizationError(
                "Authorization archive collision contains different content."
            )
        try:
            _fsync_directory(archive_directory)
        except OSError as exc:
            raise DemoExecutionAuthorizationError(
                "Unable to durably confirm the authorization archive directory."
            ) from exc
        return archive_path

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=archive_directory,
            prefix=f".{archive_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(exact_bytes)
            handle.flush()
            os.fsync(handle.fileno())

        try:
            os.link(temporary_path, archive_path)
        except FileExistsError:
            if (
                archive_path.is_symlink()
                or not archive_path.is_file()
                or _read_authorization_bytes(archive_path) != exact_bytes
            ):
                raise DemoExecutionAuthorizationError(
                    "Authorization archive collision contains different content."
                )
        temporary_path.unlink()
        temporary_path = None
        _fsync_directory(archive_directory)
    except DemoExecutionAuthorizationError:
        raise
    except OSError as exc:
        raise DemoExecutionAuthorizationError(
            "Unable to durably archive expired demo authorization."
        ) from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

    return archive_path


def _write_active_authorization_durably(
    *,
    target: Path,
    authorization: DemoExecutionAuthorization,
    replacing_existing: bool,
) -> None:
    parent = target.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DemoExecutionAuthorizationError(
            "Unable to create demo authorization directory."
        ) from exc

    serialized = (
        json.dumps(authorization.to_payload(), indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())

        if replacing_existing:
            if target.is_symlink() or not target.is_file():
                raise DemoExecutionAuthorizationError(
                    "Existing authorization disappeared before replacement."
                )
        elif os.path.lexists(target):
            raise DemoExecutionAuthorizationError(
                "A demo execution authorization appeared during creation."
            )

        os.replace(temporary_path, target)
        temporary_path = None
        _fsync_directory(parent)
    except DemoExecutionAuthorizationError:
        raise
    except OSError as exc:
        raise DemoExecutionAuthorizationError(
            "Unable to persist fresh demo execution authorization durably."
        ) from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def _read_authorization_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise DemoExecutionAuthorizationError(
            f"Unable to read authorization artifact durably: {path}"
        ) from exc


def _validated_archive_name(authorization_id: str) -> str:
    if (
        not isinstance(authorization_id, str)
        or not authorization_id
        or authorization_id in {".", ".."}
        or Path(authorization_id).name != authorization_id
        or any(char in authorization_id for char in '<>:"/\\|?*')
        or authorization_id[-1:] in {".", " "}
        or any(ord(char) < 32 for char in authorization_id)
    ):
        raise DemoExecutionAuthorizationError(
            "Authorization ID is unsafe for durable archival."
        )
    return authorization_id


def _fsync_directory(directory: Path) -> None:
    """Durably flush directory metadata on POSIX and Windows."""

    try:
        descriptor = os.open(
            directory,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
    except OSError:
        if os.name != "nt":
            raise
    else:
        try:
            os.fsync(descriptor)
            return
        except OSError:
            if os.name != "nt":
                raise
        finally:
            os.close(descriptor)

    generic_read = 0x80000000
    generic_write = 0x40000000
    file_share_read = 0x00000001
    file_share_write = 0x00000002
    file_share_delete = 0x00000004
    open_existing = 3
    file_flag_backup_semantics = 0x02000000

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    flush_file_buffers = kernel32.FlushFileBuffers
    flush_file_buffers.argtypes = (wintypes.HANDLE,)
    flush_file_buffers.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL

    handle = create_file(
        str(directory),
        generic_read | generic_write,
        file_share_read | file_share_write | file_share_delete,
        None,
        open_existing,
        file_flag_backup_semantics,
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        error = ctypes.get_last_error()
        raise OSError(error, "Unable to open directory for durable fsync.")

    try:
        if not flush_file_buffers(handle):
            error = ctypes.get_last_error()
            raise OSError(error, "Unable to fsync directory metadata.")
    finally:
        close_handle(handle)


def consume_demo_execution_authorization(
    path: str | Path,
    authorization: DemoExecutionAuthorization,
    *,
    intent_key: str,
    consumed_at: datetime,
) -> DemoExecutionAuthorization:
    if authorization.consumed:
        raise DemoExecutionAuthorizationError(
            "Demo execution authorization has already been consumed."
        )
    if not isinstance(intent_key, str) or not intent_key.strip():
        raise DemoExecutionAuthorizationError(
            "Execution intent key is required before authorization consumption."
        )
    target = Path(path)
    try:
        with _authorization_consumption_lock(target).hold():
            current = _load_demo_execution_authorization_unlocked(target)
            if current.consumed:
                raise DemoExecutionAuthorizationError(
                    "Demo execution authorization has already been consumed."
                )
            if current != authorization:
                raise DemoExecutionAuthorizationError(
                    "Demo execution authorization changed before consumption."
                )
            consumed = replace(
                current,
                consumed_at=_aware_utc(consumed_at, "consumed_at"),
                consumed_intent_key=intent_key,
            )
            temporary = target.with_name(target.name + ".tmp")
            serialized = (
                json.dumps(consumed.to_payload(), indent=2, sort_keys=True)
                + "\n"
            )
            try:
                with temporary.open(
                    "w",
                    encoding="utf-8",
                    newline="\n",
                ) as handle:
                    handle.write(serialized)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, target)
            except OSError as exc:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
                raise DemoExecutionAuthorizationError(
                    "Unable to consume demo execution authorization durably."
                ) from exc
    except ExecutionConcurrencyError as exc:
        raise DemoExecutionAuthorizationError(
            "Demo execution authorization consumption ownership is uncertain."
        ) from exc
    return consumed


def _authorization_consumption_lock(path: Path) -> LocalExecutionLock:
    return LocalExecutionLock(
        build_execution_lock_path(
            path,
            scope="authorization-consumption",
        ),
        purpose="demo authorization consumption",
    )


def _parse_datetime(value: object, name: str) -> datetime:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be an ISO-8601 string")
    return _aware_utc(datetime.fromisoformat(value), name)


def _aware_utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _strict_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    return value


def _strict_bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")
    return value
