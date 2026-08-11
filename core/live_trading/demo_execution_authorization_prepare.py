\
"""Prepare one fresh XAUUSD demo authorization from connected preflight evidence.

This module never imports MT5, never enables execution controls, and never
consumes an authorization. It creates a new grant only when the durable
authorization lifecycle policy permits it.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from math import isclose, isfinite
from pathlib import Path
from typing import Any, Final

from .config import LiveTradingConfig
from .demo_execution_authorization import (
    DemoAuthorizationPreparationResult,
    DemoExecutionAuthorizationError,
    create_fresh_demo_execution_authorization,
)
from .parity_validation_attestation import (
    ParityValidationAttestationError,
    verify_parity_validation_attestation,
)

_PREFLIGHT_PATH: Final = Path(
    "output/live_execution_reconciliation/connected_demo_canary_preflight.json"
)
_REQUIRED_ACKNOWLEDGEMENT: Final = "I AUTHORIZE ONE DEMO ORDER"
_CANARY_SYMBOL: Final = "XAUUSD"
_CANARY_VOLUME: Final = 0.01
_PREFLIGHT_MAX_AGE_SECONDS: Final = 900
_VOLUME_TOLERANCE: Final = 1e-12


class DemoAuthorizationPreparationError(RuntimeError):
    """Raised when connected preflight evidence cannot authorize preparation."""


def prepare_fresh_demo_authorization_from_preflight(
    *,
    config: LiveTradingConfig,
    preflight_path: str | Path,
    acknowledgement: str,
    now: datetime,
) -> DemoAuthorizationPreparationResult:
    observed_at = _aware_utc(now, "now")
    try:
        verify_parity_validation_attestation(config=config)
    except ParityValidationAttestationError as exc:
        raise DemoAuthorizationPreparationError(
            "Current live parity attestation is missing or incompatible."
        ) from exc
    payload = _load_preflight_payload(preflight_path)
    account_login, account_server, account_trade_mode = _validate_preflight_payload(
        payload,
        config=config,
        now=observed_at,
    )
    return create_fresh_demo_execution_authorization(
        config=config,
        account_login=account_login,
        account_server=account_server,
        account_trade_mode=account_trade_mode,
        demo_account_confirmed=True,
        acknowledgement=acknowledgement,
        now=observed_at,
    )


def _load_preflight_payload(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DemoAuthorizationPreparationError(
            "Connected demo-canary preflight evidence could not be read."
        ) from exc
    if not isinstance(payload, dict):
        raise DemoAuthorizationPreparationError(
            "Connected demo-canary preflight evidence must be a JSON object."
        )
    return payload


def _validate_preflight_payload(
    payload: dict[str, Any],
    *,
    config: LiveTradingConfig,
    now: datetime,
) -> tuple[int, str, int]:
    if payload.get("validation_passed") is not True or payload.get("reasons") != []:
        raise DemoAuthorizationPreparationError(
            "Connected demo-canary preflight did not pass cleanly."
        )
    if payload.get("symbol") != _CANARY_SYMBOL or config.symbol != _CANARY_SYMBOL:
        raise DemoAuthorizationPreparationError(
            "Fresh demo authorization is restricted to XAUUSD."
        )
    if payload.get("demo_account_confirmed") is not True:
        raise DemoAuthorizationPreparationError(
            "Connected account is not confirmed as demo."
        )
    if payload.get("symbol_trade_allowed") is not True:
        raise DemoAuthorizationPreparationError(
            "XAUUSD is not trade-allowed in connected preflight evidence."
        )
    if (
        payload.get("live_execution_enabled") is not False
        or payload.get("demo_execution_approved") is not False
        or payload.get("execution_kill_switch_enabled") is not True
    ):
        raise DemoAuthorizationPreparationError(
            "Connected preflight did not preserve safe-disabled controls."
        )
    if (
        payload.get("active_order_count") != 0
        or payload.get("open_position_count") != 0
        or payload.get("reconciliation_clear") is not True
        or payload.get("unresolved_partial_fill") is not False
        or payload.get("order_submission_attempted") is not False
        or payload.get("trade_executed") is not False
        or payload.get("authorization_consumed") is not False
    ):
        raise DemoAuthorizationPreparationError(
            "Connected preflight contains a canary lifecycle blocker."
        )
    if payload.get("persisted_intent_status") in {
        "PREPARED",
        "PENDING",
        "PARTIALLY_FILLED",
    }:
        raise DemoAuthorizationPreparationError(
            "Connected preflight contains an unresolved execution intent."
        )

    account_login = payload.get("account_login")
    account_server = payload.get("account_server")
    account_trade_mode = payload.get("account_trade_mode")
    if (
        isinstance(account_login, bool)
        or not isinstance(account_login, int)
        or account_login <= 0
    ):
        raise DemoAuthorizationPreparationError(
            "Connected preflight account login is invalid."
        )
    if (
        not isinstance(account_server, str)
        or not account_server
        or account_server != account_server.strip()
    ):
        raise DemoAuthorizationPreparationError(
            "Connected preflight account server is invalid."
        )
    if account_trade_mode != 0:
        raise DemoAuthorizationPreparationError(
            "Connected preflight account is not an MT5 demo account."
        )

    recorded_at_raw = payload.get("recorded_at")
    if not isinstance(recorded_at_raw, str):
        raise DemoAuthorizationPreparationError(
            "Connected preflight recorded_at is invalid."
        )
    try:
        recorded_at = _aware_utc(
            datetime.fromisoformat(recorded_at_raw),
            "recorded_at",
        )
    except (TypeError, ValueError) as exc:
        raise DemoAuthorizationPreparationError(
            "Connected preflight recorded_at is invalid."
        ) from exc
    age_seconds = (now - recorded_at).total_seconds()
    if age_seconds < 0.0 or age_seconds > _PREFLIGHT_MAX_AGE_SECONDS:
        raise DemoAuthorizationPreparationError(
            "Connected preflight evidence is older than 15 minutes or from "
            "the future."
        )

    volume_min = _finite_number(payload.get("symbol_volume_min"), "symbol_volume_min")
    volume_max = _finite_number(payload.get("symbol_volume_max"), "symbol_volume_max")
    volume_step = _finite_number(
        payload.get("symbol_volume_step"),
        "symbol_volume_step",
    )
    if (
        volume_step <= 0.0
        or _CANARY_VOLUME < volume_min - _VOLUME_TOLERANCE
        or _CANARY_VOLUME > volume_max + _VOLUME_TOLERANCE
    ):
        raise DemoAuthorizationPreparationError(
            "Connected XAUUSD volume bounds do not permit 0.01 lot."
        )
    steps = (_CANARY_VOLUME - volume_min) / volume_step
    if not isclose(steps, round(steps), rel_tol=0.0, abs_tol=1e-9):
        raise DemoAuthorizationPreparationError(
            "0.01 lot is not aligned to the connected XAUUSD volume step."
        )

    return account_login, account_server, account_trade_mode


def _finite_number(value: object, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(float(value))
    ):
        raise DemoAuthorizationPreparationError(
            f"Connected preflight {name} is invalid."
        )
    return float(value)


def _aware_utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create one fresh XAUUSD demo-canary authorization from the latest "
            "connected safe-disabled preflight evidence. Expired unconsumed "
            "authorization is rotated only under Authorization Retirement "
            "Policy V1."
        )
    )
    parser.add_argument(
        "--acknowledgement",
        required=True,
        help=f'Exact required text: "{_REQUIRED_ACKNOWLEDGEMENT}"',
    )
    args = parser.parse_args()

    config = LiveTradingConfig(
        symbol=_CANARY_SYMBOL,
        live_execution_enabled=False,
        demo_execution_approved=False,
        execution_kill_switch_enabled=True,
    )
    try:
        result = prepare_fresh_demo_authorization_from_preflight(
            config=config,
            preflight_path=_PREFLIGHT_PATH,
            acknowledgement=args.acknowledgement,
            now=datetime.now(UTC),
        )
    except (
        DemoAuthorizationPreparationError,
        DemoExecutionAuthorizationError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"Fresh demo authorization preparation failed closed: {exc}")
        return 2

    authorization = result.authorization
    print(
        json.dumps(
            {
                "authorization_id": authorization.authorization_id,
                "account_login": authorization.account_login,
                "account_server": authorization.account_server,
                "symbol": authorization.symbol,
                "maximum_volume": authorization.maximum_volume,
                "maximum_submissions": authorization.maximum_submissions,
                "issued_at": authorization.issued_at.isoformat(),
                "expires_at": authorization.expires_at.isoformat(),
                "consumed": authorization.consumed,
                "archived_authorization_path": (
                    None
                    if result.archived_authorization_path is None
                    else str(result.archived_authorization_path)
                ),
                "rotated_expired_authorization": (
                    result.rotated_expired_authorization
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
