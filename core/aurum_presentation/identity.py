"""Pure identity and UTC-normalization helpers for Aurum snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4


def require_aware_utc(value: datetime, *, name: str) -> datetime:
    """Return ``value`` normalized to UTC, rejecting naive datetimes."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def utc_z(value: datetime, *, name: str = "datetime") -> str:
    """Serialize a timezone-aware datetime as canonical UTC ISO-8601 with Z."""

    normalized = require_aware_utc(value, name=name)
    return normalized.isoformat().replace("+00:00", "Z")


def build_observation_id(
    *,
    symbol: str,
    observation_time_utc: datetime,
) -> str:
    """Return stable ``SYMBOL|M5|UTC_Z`` identity for one M5 observation."""

    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol must be non-empty")
    return f"{normalized_symbol}|M5|{utc_z(observation_time_utc, name='observation_time_utc')}"


def build_snapshot_id() -> str:
    """Return a unique identity for one complete serialized snapshot."""

    return str(uuid4())
