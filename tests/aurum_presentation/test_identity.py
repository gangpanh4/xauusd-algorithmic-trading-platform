from datetime import UTC, datetime, timedelta, timezone

import pytest

from core.aurum_presentation.identity import build_observation_id, build_snapshot_id


def test_observation_id_is_stable_and_normalizes_timezone() -> None:
    utc = datetime(2026, 8, 16, 8, 30, tzinfo=UTC)
    offset = datetime(2026, 8, 16, 15, 30, tzinfo=timezone(timedelta(hours=7)))
    assert build_observation_id(symbol="xauusd", observation_time_utc=utc) == (
        "XAUUSD|M5|2026-08-16T08:30:00Z"
    )
    assert build_observation_id(symbol="XAUUSD", observation_time_utc=offset) == (
        build_observation_id(symbol="xauusd", observation_time_utc=utc)
    )


def test_different_observation_has_different_id() -> None:
    first = datetime(2026, 8, 16, 8, 30, tzinfo=UTC)
    second = first + timedelta(minutes=5)
    assert build_observation_id(symbol="XAUUSD", observation_time_utc=first) != (
        build_observation_id(symbol="XAUUSD", observation_time_utc=second)
    )


def test_naive_observation_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        build_observation_id(
            symbol="XAUUSD",
            observation_time_utc=datetime(2026, 8, 16, 8, 30),  # noqa: DTZ001
        )


def test_snapshot_ids_are_unique_uuid_strings() -> None:
    first = build_snapshot_id()
    second = build_snapshot_id()
    assert first != second
    assert len(first) == 36
