"""Durable unresolved partial-fill state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from math import isclose, isfinite
import os
from pathlib import Path
import tempfile
from typing import Any

_SCHEMA_VERSION = 1
_EXPECTED_KEYS = {
    "version",
    "symbol",
    "ticket",
    "requested_volume",
    "executed_volume",
    "remaining_volume",
    "created_at",
}


class PartialFillStateError(RuntimeError):
    """Raised when durable partial-fill state cannot be trusted."""


@dataclass(frozen=True)
class PersistedPartialFill:
    """Validated unresolved partial-fill record."""

    symbol: str
    ticket: int
    requested_volume: float
    executed_volume: float
    remaining_volume: float
    created_at: datetime


class PartialFillStateStore:
    """Read and atomically replace one unresolved partial-fill record."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> PersistedPartialFill | None:
        """Load a validated record, or return None when no file exists."""

        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise PartialFillStateError(
                f"Unable to read partial-fill state: {self.path}"
            ) from exc

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PartialFillStateError(
                "Partial-fill state is not valid JSON."
            ) from exc

        return self._decode(payload)

    def save(self, record: PersistedPartialFill) -> None:
        """Validate and atomically persist the unresolved record."""

        validated = self._validate_record(record)
        payload = {
            "version": _SCHEMA_VERSION,
            "symbol": validated.symbol,
            "ticket": validated.ticket,
            "requested_volume": validated.requested_volume,
            "executed_volume": validated.executed_volume,
            "remaining_volume": validated.remaining_volume,
            "created_at": validated.created_at.isoformat(),
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
            raise PartialFillStateError(
                f"Unable to create partial-fill state directory: {parent}"
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
            raise PartialFillStateError(
                f"Unable to persist partial-fill state: {self.path}"
            ) from exc
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except FileNotFoundError:
                    pass
                except OSError:
                    pass

    def clear(self) -> None:
        """Remove terminal state; a missing file is already clear."""

        try:
            self.path.unlink()
        except FileNotFoundError:
            return
        except OSError as exc:
            raise PartialFillStateError(
                f"Unable to clear partial-fill state: {self.path}"
            ) from exc

    @classmethod
    def _decode(cls, payload: Any) -> PersistedPartialFill:
        if not isinstance(payload, dict):
            raise PartialFillStateError(
                "Partial-fill state root must be a JSON object."
            )

        keys = set(payload)
        if keys != _EXPECTED_KEYS:
            missing = sorted(_EXPECTED_KEYS - keys)
            unexpected = sorted(keys - _EXPECTED_KEYS)
            raise PartialFillStateError(
                "Partial-fill state schema mismatch: "
                f"missing={missing}, unexpected={unexpected}."
            )

        version = payload["version"]
        if (
            isinstance(version, bool)
            or not isinstance(version, int)
            or version != _SCHEMA_VERSION
        ):
            raise PartialFillStateError(
                f"Unsupported partial-fill state version: {version!r}."
            )

        created_at_raw = payload["created_at"]
        if not isinstance(created_at_raw, str):
            raise PartialFillStateError(
                "Partial-fill created_at must be an ISO-8601 string."
            )
        try:
            created_at = datetime.fromisoformat(created_at_raw)
        except ValueError as exc:
            raise PartialFillStateError(
                "Partial-fill created_at is not valid ISO-8601."
            ) from exc

        record = PersistedPartialFill(
            symbol=payload["symbol"],
            ticket=payload["ticket"],
            requested_volume=payload["requested_volume"],
            executed_volume=payload["executed_volume"],
            remaining_volume=payload["remaining_volume"],
            created_at=created_at,
        )
        return cls._validate_record(record)

    @staticmethod
    def _validate_record(
        record: PersistedPartialFill,
    ) -> PersistedPartialFill:
        if not isinstance(record, PersistedPartialFill):
            raise PartialFillStateError(
                "Partial-fill state record has an invalid type."
            )
        if not isinstance(record.symbol, str) or not record.symbol.strip():
            raise PartialFillStateError(
                "Partial-fill symbol must be a non-empty string."
            )
        if (
            isinstance(record.ticket, bool)
            or not isinstance(record.ticket, int)
            or record.ticket <= 0
        ):
            raise PartialFillStateError(
                "Partial-fill ticket must be a positive integer."
            )
        if record.created_at.tzinfo is None:
            raise PartialFillStateError(
                "Partial-fill created_at must include a timezone."
            )

        volumes = (
            record.requested_volume,
            record.executed_volume,
            record.remaining_volume,
        )
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(float(value))
            for value in volumes
        ):
            raise PartialFillStateError(
                "Partial-fill volumes must be finite numbers."
            )

        requested = float(record.requested_volume)
        executed = float(record.executed_volume)
        remaining = float(record.remaining_volume)
        if requested <= 0.0 or executed <= 0.0 or remaining <= 0.0:
            raise PartialFillStateError(
                "Partial-fill volumes must be positive."
            )
        if executed >= requested:
            raise PartialFillStateError(
                "Executed partial-fill volume must be below requested volume."
            )
        if not isclose(
            requested - executed,
            remaining,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise PartialFillStateError(
                "Partial-fill volumes are internally inconsistent."
            )

        return PersistedPartialFill(
            symbol=record.symbol,
            ticket=record.ticket,
            requested_volume=requested,
            executed_volume=executed,
            remaining_volume=remaining,
            created_at=record.created_at,
        )
