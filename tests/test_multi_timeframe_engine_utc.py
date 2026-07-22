from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from core.multi_timeframe.config import MultiTimeframeConfig
from core.multi_timeframe.engine import MultiTimeframeEngine
from core.multi_timeframe.enums import MarketBias, Timeframe, TimeframeAlignment
from core.multi_timeframe.manager import MultiTimeframeManager
from core.multi_timeframe.models import TimeframeState


def _ready_manager(
    *,
    biases: tuple[MarketBias, ...] | None = None,
    alignments: tuple[TimeframeAlignment, ...] | None = None,
    confidences: tuple[float, ...] | None = None,
) -> MultiTimeframeManager:
    config = MultiTimeframeConfig()
    manager = MultiTimeframeManager(config)
    base = datetime(2026, 1, 1, tzinfo=UTC)

    biases = biases or (MarketBias.BULLISH,) * 6
    alignments = alignments or (TimeframeAlignment.ALIGNED,) * 6
    confidences = confidences or (0.75,) * 6

    for index, timeframe in enumerate(config.active_timeframes):
        manager.update(
            timeframe,
            TimeframeState(
                timeframe=timeframe,
                timestamp=base + timedelta(minutes=index),
                bias=biases[index],
                alignment=alignments[index],
                confidence=confidences[index],
            ),
        )
    return manager


def test_result_timestamp_is_newest_completed_snapshot_timestamp() -> None:
    manager = _ready_manager()

    result = MultiTimeframeEngine().process(manager)

    assert result.timestamp == datetime(2026, 1, 1, 0, 5, tzinfo=UTC)
    assert result.timestamp.tzinfo is UTC
    assert manager.state.latest_result is result


def test_non_utc_snapshot_timestamps_are_normalized_to_utc() -> None:
    config = MultiTimeframeConfig()
    manager = MultiTimeframeManager(config)
    plus_seven = timezone(timedelta(hours=7))
    base = datetime(2026, 1, 1, 7, tzinfo=plus_seven)

    for index, timeframe in enumerate(config.active_timeframes):
        manager.update(
            timeframe,
            TimeframeState(
                timeframe=timeframe,
                timestamp=base + timedelta(minutes=index),
                confidence=0.5,
            ),
        )

    result = MultiTimeframeEngine(config).process(manager)

    assert result.timestamp == datetime(2026, 1, 1, 0, 5, tzinfo=UTC)
    assert result.timestamp.tzinfo is UTC


def test_aggregate_bias_alignment_and_confidence_preserve_existing_semantics() -> None:
    manager = _ready_manager(
        biases=(
            MarketBias.BULLISH,
            MarketBias.BULLISH,
            MarketBias.BULLISH,
            MarketBias.BEARISH,
            MarketBias.NEUTRAL,
            MarketBias.BEARISH,
        ),
        alignments=(
            TimeframeAlignment.ALIGNED,
            TimeframeAlignment.ALIGNED,
            TimeframeAlignment.ALIGNED,
            TimeframeAlignment.CONFLICT,
            TimeframeAlignment.PARTIAL,
            TimeframeAlignment.CONFLICT,
        ),
        confidences=(0.2, 0.4, 0.6, 0.8, 1.0, 0.0),
    )

    result = MultiTimeframeEngine().process(manager)

    assert result.overall_bias is MarketBias.BULLISH
    assert result.overall_alignment is TimeframeAlignment.PARTIAL
    assert result.confidence == pytest.approx(0.5)


def test_tied_direction_remains_neutral() -> None:
    manager = _ready_manager(
        biases=(
            MarketBias.BULLISH,
            MarketBias.BULLISH,
            MarketBias.BEARISH,
            MarketBias.BEARISH,
            MarketBias.NEUTRAL,
            MarketBias.NEUTRAL,
        )
    )

    assert MultiTimeframeEngine().process(manager).overall_bias is MarketBias.NEUTRAL


def test_naive_snapshot_timestamp_fails_before_latest_result_commit() -> None:
    manager = _ready_manager()
    state = manager.state.timeframe_states[Timeframe.H4]
    state.timestamp = datetime(2026, 1, 1)
    previous = manager.state.latest_result

    with pytest.raises(ValueError, match="timezone-aware"):
        MultiTimeframeEngine().process(manager)

    assert manager.state.latest_result is previous


def test_missing_snapshot_timestamp_fails_closed() -> None:
    manager = _ready_manager()
    manager.state.timeframe_states[Timeframe.M15].timestamp = None

    with pytest.raises(ValueError, match="must not be None"):
        MultiTimeframeEngine().process(manager)


def test_engine_rejects_manager_configuration_mismatch() -> None:
    manager = _ready_manager()
    reordered = replace(
        MultiTimeframeConfig(),
        hierarchy=(
            Timeframe.DAILY,
            Timeframe.WEEKLY,
            Timeframe.H4,
            Timeframe.H1,
            Timeframe.M15,
            Timeframe.M5,
        ),
    )

    with pytest.raises(ValueError, match="hierarchy must be ordered"):
        MultiTimeframeEngine(reordered).process(manager)


def test_engine_rejects_incomplete_manager() -> None:
    manager = MultiTimeframeManager()

    with pytest.raises(RuntimeError, match="not fully initialized"):
        MultiTimeframeEngine().process(manager)
