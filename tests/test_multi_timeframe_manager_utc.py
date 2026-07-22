from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from core.multi_timeframe.config import MultiTimeframeConfig
from core.multi_timeframe.enums import Timeframe
from core.multi_timeframe.manager import MultiTimeframeManager
from core.multi_timeframe.models import TimeframeState


def _state(
    timeframe: Timeframe,
    *,
    confidence: float = 0.75,
    timestamp: datetime | None = None,
) -> TimeframeState:
    return TimeframeState(
        timeframe=timeframe,
        confidence=confidence,
        timestamp=timestamp or datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_update_uses_utc_aware_clock_and_preserves_previous_state() -> None:
    moments = iter(
        (
            datetime(2026, 1, 1, 12, tzinfo=UTC),
            datetime(2026, 1, 1, 13, tzinfo=UTC),
            datetime(2026, 1, 1, 14, tzinfo=UTC),
        )
    )
    manager = MultiTimeframeManager(clock=lambda: next(moments))
    first = _state(Timeframe.H4, confidence=0.6)
    second = _state(Timeframe.H4, confidence=0.8)

    manager.update(Timeframe.H4, first)
    manager.update(Timeframe.H4, second)

    assert manager.get_state(Timeframe.H4) is second
    assert manager.state.previous_states[Timeframe.H4] is first
    assert manager.state.processed_updates == 2
    assert manager.state.last_updated == datetime(2026, 1, 1, 14, tzinfo=UTC)
    assert manager.state.last_updated.tzinfo is UTC


def test_clock_is_normalized_to_utc() -> None:
    local_tz = timezone(timedelta(hours=7))
    moments = iter(
        (
            datetime(2026, 1, 1, 12, tzinfo=local_tz),
            datetime(2026, 1, 1, 13, tzinfo=local_tz),
        )
    )
    manager = MultiTimeframeManager(clock=lambda: next(moments))

    manager.update(Timeframe.M15, _state(Timeframe.M15))

    assert manager.state.last_updated == datetime(2026, 1, 1, 6, tzinfo=UTC)


def test_failed_update_is_transactional() -> None:
    manager = MultiTimeframeManager(
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    valid = _state(Timeframe.H1)
    manager.update(Timeframe.H1, valid)
    before_updates = manager.state.processed_updates
    before_timestamp = manager.state.last_updated

    with pytest.raises(ValueError, match="must match"):
        manager.update(Timeframe.H1, _state(Timeframe.M15))

    assert manager.get_state(Timeframe.H1) is valid
    assert manager.state.processed_updates == before_updates
    assert manager.state.last_updated == before_timestamp
    assert Timeframe.H1 not in manager.state.previous_states


def test_inactive_timeframe_fails_closed() -> None:
    config = MultiTimeframeConfig(active_timeframes=(Timeframe.M15,))
    manager = MultiTimeframeManager(
        config,
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="not active"):
        manager.update(Timeframe.H4, _state(Timeframe.H4))


def test_naive_analysis_timestamp_is_rejected() -> None:
    manager = MultiTimeframeManager(
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )

    with pytest.raises(ValueError, match="analysis.timestamp"):
        manager.update(
            Timeframe.M15,
            _state(Timeframe.M15, timestamp=datetime(2026, 1, 1)),
        )


def test_naive_or_non_datetime_clock_fails_closed() -> None:
    with pytest.raises(ValueError, match="clock result"):
        MultiTimeframeManager(clock=lambda: datetime(2026, 1, 1))

    with pytest.raises(TypeError, match="clock result"):
        MultiTimeframeManager(clock=lambda: "not-a-datetime")  # type: ignore[arg-type]


def test_invalid_confidence_does_not_mutate_state() -> None:
    manager = MultiTimeframeManager(
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )

    with pytest.raises(ValueError, match="between 0 and 1"):
        manager.update(
            Timeframe.M5,
            _state(Timeframe.M5, confidence=1.01),
        )

    assert manager.state.processed_updates == 0
    assert manager.state.last_updated is None
    assert not manager.state.initialized


def test_reset_clears_utc_snapshot_state() -> None:
    moments = iter(
        (
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 2, tzinfo=UTC),
        )
    )
    manager = MultiTimeframeManager(clock=lambda: next(moments))
    manager.update(Timeframe.M5, _state(Timeframe.M5))

    manager.reset()

    assert manager.state.timeframe_states == {}
    assert manager.state.previous_states == {}
    assert manager.state.processed_updates == 0
    assert manager.state.last_updated is None
    assert not manager.state.initialized
