"""Fail-closed one-shot authorization for MT5 demo order submission."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path
from typing import Any, Final

from core.mt5_execution.models import AccountInfo, OrderRequest

from .config import LiveTradingConfig

_SCHEMA_VERSION: Final = 1
_DEMO_TRADE_MODE: Final = 0
_REQUIRED_ACKNOWLEDGEMENT: Final = "I AUTHORIZE ONE DEMO ORDER"


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


def validate_demo_execution_authorization(
    authorization: DemoExecutionAuthorization,
    *,
    config: LiveTradingConfig,
    account: AccountInfo,
    request: OrderRequest,
    now: datetime,
) -> None:
    observed_at = _aware_utc(now, "now")
    if authorization.schema_version != _SCHEMA_VERSION:
        raise DemoExecutionAuthorizationError(
            "Unsupported demo authorization schema version."
        )
    if not authorization.authorization_id.strip():
        raise DemoExecutionAuthorizationError("Demo authorization ID is empty.")
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
        raise DemoExecutionAuthorizationError("Execution kill switch is enabled.")
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
    if authorization.symbol != config.symbol or request.symbol != config.symbol:
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
    lifetime = (authorization.expires_at - authorization.issued_at).total_seconds()
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
    if observed_at < authorization.issued_at:
        raise DemoExecutionAuthorizationError("Demo authorization is not active yet.")
    if observed_at > authorization.expires_at:
        raise DemoExecutionAuthorizationError("Demo authorization has expired.")
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
    consumed = replace(
        authorization,
        consumed_at=_aware_utc(consumed_at, "consumed_at"),
        consumed_intent_key=intent_key,
    )
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    serialized = json.dumps(consumed.to_payload(), indent=2, sort_keys=True) + "\n"
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
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
    return consumed


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
