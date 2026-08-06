"""Durable idempotency state for one broker execution intent."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from hashlib import sha256
from math import isfinite
from pathlib import Path
from typing import Any

from core.mt5_execution.models import OrderRequest, OrderResult, OrderStatus

_SCHEMA_VERSION = 2
_EXPECTED_KEYS = {
    "version",
    "intent_key",
    "symbol",
    "observation_timestamp",
    "side",
    "volume",
    "entry_price",
    "stop_loss",
    "take_profit",
    "status",
    "ticket",
    "created_at",
    "updated_at",
    "magic_number",
    "broker_comment",
}


class ExecutionIntentStateError(RuntimeError):
    """Raised when durable execution-intent state cannot be trusted."""


class ExecutionIntentStatus(Enum):
    """Durable lifecycle states for one broker submission decision."""

    PREPARED = "PREPARED"
    PENDING = "PENDING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

    @property
    def unresolved(self) -> bool:
        return self in {
            ExecutionIntentStatus.PREPARED,
            ExecutionIntentStatus.PENDING,
            ExecutionIntentStatus.PARTIALLY_FILLED,
        }


@dataclass(frozen=True, slots=True)
class PersistedExecutionIntent:
    """Validated durable identity and outcome for one execution request."""

    intent_key: str
    symbol: str
    observation_timestamp: datetime
    side: str
    volume: float
    entry_price: float
    stop_loss: float
    take_profit: float
    status: ExecutionIntentStatus
    ticket: int | None
    created_at: datetime
    updated_at: datetime
    magic_number: int
    broker_comment: str

    @property
    def unresolved(self) -> bool:
        return self.status.unresolved


def build_execution_intent(
    *,
    observation_timestamp: datetime,
    request: OrderRequest,
    created_at: datetime | None = None,
    magic_number: int = 0,
) -> PersistedExecutionIntent:
    """Build a deterministic intent key before any broker submission."""

    timestamp = _aware_utc(observation_timestamp, "observation_timestamp")
    now = datetime.now(UTC) if created_at is None else _aware_utc(
        created_at,
        "created_at",
    )
    side = request.side.value
    validated_magic = _non_negative_int(magic_number, "magic_number")
    numeric = {
        "volume": _finite(request.volume, "volume", positive=True),
        "entry_price": _finite(request.entry_price, "entry_price"),
        "stop_loss": _finite(request.stop_loss, "stop_loss", positive=True),
        "take_profit": _finite(
            request.take_profit,
            "take_profit",
            positive=True,
        ),
    }
    if not isinstance(request.symbol, str) or not request.symbol.strip():
        raise ExecutionIntentStateError("Execution-intent symbol is invalid.")

    canonical = json.dumps(
        {
            "symbol": request.symbol,
            "observation_timestamp": timestamp.isoformat(),
            "side": side,
            "magic_number": validated_magic,
            **numeric,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    intent_key = sha256(canonical.encode("utf-8")).hexdigest()
    broker_comment = f"xau:{intent_key[:16]}"

    return PersistedExecutionIntent(
        intent_key=intent_key,
        symbol=request.symbol,
        observation_timestamp=timestamp,
        side=side,
        volume=numeric["volume"],
        entry_price=numeric["entry_price"],
        stop_loss=numeric["stop_loss"],
        take_profit=numeric["take_profit"],
        status=ExecutionIntentStatus.PREPARED,
        ticket=None,
        created_at=now,
        updated_at=now,
        magic_number=validated_magic,
        broker_comment=broker_comment,
    )


def apply_execution_result(
    intent: PersistedExecutionIntent,
    result: OrderResult,
) -> PersistedExecutionIntent:
    """Return the durable broker outcome for a previously prepared intent."""

    status_map = {
        OrderStatus.PENDING: ExecutionIntentStatus.PENDING,
        OrderStatus.PARTIALLY_FILLED: ExecutionIntentStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED: ExecutionIntentStatus.FILLED,
        OrderStatus.REJECTED: ExecutionIntentStatus.REJECTED,
        OrderStatus.CANCELLED: ExecutionIntentStatus.CANCELLED,
    }
    return replace(
        intent,
        status=status_map[result.status],
        ticket=result.ticket,
        updated_at=_aware_utc(result.timestamp, "result.timestamp"),
    )


class ExecutionIntentStore:
    """Atomically persist the latest execution intent and broker outcome."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> PersistedExecutionIntent | None:
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise ExecutionIntentStateError(
                f"Unable to read execution-intent state: {self.path}"
            ) from exc

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ExecutionIntentStateError(
                "Execution-intent state is not valid JSON."
            ) from exc
        return self._decode(payload)

    def save(self, intent: PersistedExecutionIntent) -> None:
        validated = self._validate(intent)
        payload = {
            "version": _SCHEMA_VERSION,
            "intent_key": validated.intent_key,
            "symbol": validated.symbol,
            "observation_timestamp": (
                validated.observation_timestamp.isoformat()
            ),
            "side": validated.side,
            "volume": validated.volume,
            "entry_price": validated.entry_price,
            "stop_loss": validated.stop_loss,
            "take_profit": validated.take_profit,
            "status": validated.status.value,
            "ticket": validated.ticket,
            "created_at": validated.created_at.isoformat(),
            "updated_at": validated.updated_at.isoformat(),
            "magic_number": validated.magic_number,
            "broker_comment": validated.broker_comment,
        }
        serialized = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n"

        parent = self.path.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ExecutionIntentStateError(
                f"Unable to create execution-intent directory: {parent}"
            ) from exc

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.path)
            temporary_path = None
        except OSError as exc:
            raise ExecutionIntentStateError(
                f"Unable to persist execution-intent state: {self.path}"
            ) from exc
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    @classmethod
    def _decode(cls, payload: Any) -> PersistedExecutionIntent:
        if not isinstance(payload, dict):
            raise ExecutionIntentStateError(
                "Execution-intent state root must be a JSON object."
            )
        if set(payload) != _EXPECTED_KEYS:
            raise ExecutionIntentStateError(
                "Execution-intent state schema mismatch."
            )
        if payload["version"] != _SCHEMA_VERSION:
            raise ExecutionIntentStateError(
                "Unsupported execution-intent state version."
            )
        try:
            intent = PersistedExecutionIntent(
                intent_key=payload["intent_key"],
                symbol=payload["symbol"],
                observation_timestamp=datetime.fromisoformat(
                    payload["observation_timestamp"]
                ),
                side=payload["side"],
                volume=payload["volume"],
                entry_price=payload["entry_price"],
                stop_loss=payload["stop_loss"],
                take_profit=payload["take_profit"],
                status=ExecutionIntentStatus(payload["status"]),
                ticket=payload["ticket"],
                created_at=datetime.fromisoformat(payload["created_at"]),
                updated_at=datetime.fromisoformat(payload["updated_at"]),
                magic_number=payload["magic_number"],
                broker_comment=payload["broker_comment"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ExecutionIntentStateError(
                "Execution-intent state contains invalid values."
            ) from exc
        return cls._validate(intent)

    @staticmethod
    def _validate(
        intent: PersistedExecutionIntent,
    ) -> PersistedExecutionIntent:
        if not isinstance(intent, PersistedExecutionIntent):
            raise ExecutionIntentStateError(
                "Execution-intent record has an invalid type."
            )
        if (
            not isinstance(intent.intent_key, str)
            or len(intent.intent_key) != 64
            or any(
                char not in "0123456789abcdef"
                for char in intent.intent_key
            )
        ):
            raise ExecutionIntentStateError(
                "Execution-intent key is invalid."
            )
        if not isinstance(intent.symbol, str) or not intent.symbol.strip():
            raise ExecutionIntentStateError(
                "Execution-intent symbol is invalid."
            )
        if not isinstance(intent.side, str) or not intent.side:
            raise ExecutionIntentStateError(
                "Execution-intent side is invalid."
            )
        if (
            intent.ticket is not None
            and (
                isinstance(intent.ticket, bool)
                or not isinstance(intent.ticket, int)
                or intent.ticket <= 0
            )
        ):
            raise ExecutionIntentStateError(
                "Execution-intent ticket is invalid."
            )

        validated_magic = _non_negative_int(
            intent.magic_number,
            "magic_number",
        )
        expected_comment = f"xau:{intent.intent_key[:16]}"
        if intent.broker_comment != expected_comment:
            raise ExecutionIntentStateError(
                "Execution-intent broker comment is invalid."
            )

        observation = _aware_utc(
            intent.observation_timestamp,
            "observation_timestamp",
        )
        created = _aware_utc(intent.created_at, "created_at")
        updated = _aware_utc(intent.updated_at, "updated_at")
        if updated < created:
            raise ExecutionIntentStateError(
                "Execution-intent updated_at precedes created_at."
            )
        return replace(
            intent,
            observation_timestamp=observation,
            volume=_finite(intent.volume, "volume", positive=True),
            entry_price=_finite(intent.entry_price, "entry_price"),
            stop_loss=_finite(
                intent.stop_loss,
                "stop_loss",
                positive=True,
            ),
            take_profit=_finite(
                intent.take_profit,
                "take_profit",
                positive=True,
            ),
            created_at=created,
            updated_at=updated,
            magic_number=validated_magic,
        )


def _aware_utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ExecutionIntentStateError(f"{name} must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ExecutionIntentStateError(
            f"{name} must be timezone-aware."
        )
    return value.astimezone(UTC)


def _finite(
    value: float,
    name: str,
    *,
    positive: bool = False,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(float(value))
    ):
        raise ExecutionIntentStateError(f"{name} must be finite.")
    numeric = float(value)
    if positive and numeric <= 0.0:
        raise ExecutionIntentStateError(
            f"{name} must be greater than zero."
        )
    return numeric


def _non_negative_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ExecutionIntentStateError(f"{name} must be an integer.")
    if value < 0:
        raise ExecutionIntentStateError(f"{name} cannot be negative.")
    return value
