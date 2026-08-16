"""Atomic in-memory publication of the latest complete Aurum snapshot."""

from __future__ import annotations

from threading import Lock

from .models import AurumReadModelV1


class AurumSnapshotPublication:
    """Store and replace one complete immutable snapshot reference atomically."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._latest: AurumReadModelV1 | None = None

    def publish(self, snapshot: AurumReadModelV1) -> None:
        """Atomically replace the latest complete snapshot reference."""

        if not isinstance(snapshot, AurumReadModelV1):
            raise TypeError("snapshot must be an AurumReadModelV1")
        with self._lock:
            self._latest = snapshot

    def latest(self) -> AurumReadModelV1 | None:
        """Return the latest complete snapshot, if one has been published."""

        with self._lock:
            return self._latest
