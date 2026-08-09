"""Deterministic cross-process ownership for local execution mutations."""

from __future__ import annotations

import json
import os
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final
from uuid import uuid4

_LOCK_SCHEMA_VERSION: Final = 1
_OWNER_FILE_NAME: Final = "owner.json"


class ExecutionConcurrencyError(RuntimeError):
    """Raised when local execution ownership cannot be established safely."""


@dataclass(frozen=True, slots=True)
class ExecutionLockOwner:
    """Durable identity for one acquired local execution lock."""

    schema_version: int
    owner_id: str
    process_id: int
    hostname: str
    acquired_at: datetime
    purpose: str

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["acquired_at"] = self.acquired_at.astimezone(UTC).isoformat()
        return payload


def build_execution_lock_path(
    target: str | Path,
    *,
    scope: str,
) -> Path:
    """Return a deterministic sibling lock-directory path for ``target``."""

    normalized_scope = scope.strip()
    if not normalized_scope or any(
        character not in "abcdefghijklmnopqrstuvwxyz0123456789-_"
        for character in normalized_scope
    ):
        raise ValueError("Execution lock scope is invalid.")
    path = Path(target)
    if not path.name:
        raise ValueError("Execution lock target must have a filename.")
    return path.with_name(f"{path.name}.{normalized_scope}.lock")


class LocalExecutionLock:
    """An immediate, fail-closed lock based on atomic directory creation.

    Acquisition never waits. An existing directory or file is treated as
    active, stale, or otherwise uncertain ownership and is never removed
    automatically. A clean owner may release only after its durable metadata
    is read back unchanged.
    """

    def __init__(self, path: str | Path, *, purpose: str) -> None:
        self.path = Path(path)
        self.purpose = purpose.strip()
        if not self.path.name:
            raise ValueError("Execution lock path must have a name.")
        if not self.purpose:
            raise ValueError("Execution lock purpose is required.")

    @property
    def owner_path(self) -> Path:
        return self.path / _OWNER_FILE_NAME

    def assert_clear(self) -> None:
        """Fail if any active, stale, or unknown lock artifact exists."""

        if os.path.lexists(self.path):
            raise ExecutionConcurrencyError(
                f"{self.purpose} ownership already exists or is uncertain: "
                f"{self.path}"
            )

    def acquire(self) -> ExecutionLockOwner:
        """Acquire ownership once without waiting or stale-lock guessing."""

        owner = ExecutionLockOwner(
            schema_version=_LOCK_SCHEMA_VERSION,
            owner_id=str(uuid4()),
            process_id=os.getpid(),
            hostname=socket.gethostname(),
            acquired_at=datetime.now(UTC),
            purpose=self.purpose,
        )
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.mkdir()
        except FileExistsError as exc:
            raise ExecutionConcurrencyError(
                f"{self.purpose} ownership is already held or stale: "
                f"{self.path}"
            ) from exc
        except OSError as exc:
            raise ExecutionConcurrencyError(
                f"Unable to acquire {self.purpose} ownership: {self.path}"
            ) from exc

        serialized = json.dumps(
            owner.to_payload(),
            indent=2,
            sort_keys=True,
        ) + "\n"
        try:
            with self.owner_path.open(
                "x",
                encoding="utf-8",
                newline="\n",
            ) as handle:
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            # The atomic directory remains deliberately. A process crash or
            # incomplete owner record must require explicit operator review.
            raise ExecutionConcurrencyError(
                f"Unable to persist {self.purpose} owner metadata; "
                "ownership remains fail-closed."
            ) from exc
        return owner

    def release(self, owner: ExecutionLockOwner) -> None:
        """Release only ownership whose durable identity matches exactly."""

        if not isinstance(owner, ExecutionLockOwner):
            raise ExecutionConcurrencyError(
                f"Cannot release {self.purpose} without a valid owner."
            )
        try:
            payload = json.loads(self.owner_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ExecutionConcurrencyError(
                f"Cannot verify {self.purpose} ownership; lock retained."
            ) from exc
        if payload != owner.to_payload():
            raise ExecutionConcurrencyError(
                f"Cannot release foreign or changed {self.purpose} ownership; "
                "lock retained."
            )

        try:
            self.owner_path.unlink()
            self.path.rmdir()
        except OSError as exc:
            # Partial cleanup is still fail-closed because the lock directory
            # itself remains after any incomplete release.
            raise ExecutionConcurrencyError(
                f"Unable to release {self.purpose} ownership cleanly; "
                "lock retained."
            ) from exc

    @contextmanager
    def hold(self) -> Iterator[ExecutionLockOwner]:
        """Acquire and owner-verify release around one critical region."""

        owner = self.acquire()
        try:
            yield owner
        finally:
            self.release(owner)
