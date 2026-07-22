from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.data.models import MarketBar
from core.multi_timeframe.config import MultiTimeframeConfig
from core.multi_timeframe.coordinator import MultiTimeframeCoordinator
from core.multi_timeframe.enums import MarketBias, Timeframe, TimeframeAlignment
from core.multi_timeframe.models import TimeframeState


class RecordingAnalyzer:
    """Small deterministic analyzer used to verify coordinator ownership."""

    created: list["RecordingAnalyzer"] = []
    fail_on: Timeframe | None = None
    wrong_state_on: Timeframe | None = None

    def __init__(self) -> None:
        self.reset_calls = 0
        self.analyze_calls: list[tuple[Timeframe, tuple[MarketBar, ...]]] = []
        self.created.append(self)

    def reset(self) -> None:
        self.reset_calls += 1

    def analyze(
        self,
        *,
        timeframe: Timeframe,
        bars: list[MarketBar] | tuple[MarketBar, ...],
    ) -> TimeframeState:
        if timeframe is self.fail_on:
            raise RuntimeError(f"failed {timeframe.value}")

        immutable_bars = tuple(bars)
        self.analyze_calls.append((timeframe, immutable_bars))

        returned_timeframe = (
            Timeframe.M5
            if timeframe is self.wrong_state_on and timeframe is not Timeframe.M5
            else Timeframe.M15
            if timeframe is self.wrong_state_on
            else timeframe
        )

        return TimeframeState(
            timeframe=returned_timeframe,
            timestamp=immutable_bars[-1].timestamp,
            bias=MarketBias.BULLISH,
            alignment=TimeframeAlignment.ALIGNED,
            confidence=0.75,
        )


@pytest.fixture(autouse=True)
def _reset_recording_analyzer() -> None:
    RecordingAnalyzer.created = []
    RecordingAnalyzer.fail_on = None
    RecordingAnalyzer.wrong_state_on = None


def _bars_by_timeframe() -> dict[Timeframe, list[MarketBar]]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    return {
        timeframe: [
            MarketBar(
                timestamp=base + timedelta(minutes=index),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                tick_volume=100,
            )
        ]
        for index, timeframe in enumerate(Timeframe)
    }


def test_coordinator_owns_one_distinct_analyzer_per_timeframe() -> None:
    coordinator = MultiTimeframeCoordinator(
        analyzer_factory=RecordingAnalyzer,
    )

    assert set(coordinator.analyzers) == set(Timeframe)
    assert len({id(value) for value in coordinator.analyzers.values()}) == 6
    assert coordinator.analyzer is coordinator.get_analyzer(Timeframe.M15)

    coordinator.process(_bars_by_timeframe())

    for timeframe, analyzer in coordinator.analyzers.items():
        assert analyzer.reset_calls == 1
        assert [call[0] for call in analyzer.analyze_calls] == [timeframe]


def test_repeated_full_snapshot_replay_resets_each_timeframe_analyzer() -> None:
    coordinator = MultiTimeframeCoordinator(
        analyzer_factory=RecordingAnalyzer,
    )
    bars = _bars_by_timeframe()

    first = coordinator.process(bars)
    second = coordinator.process(bars)

    assert first.overall_bias is MarketBias.BULLISH
    assert second.overall_bias is MarketBias.BULLISH

    for analyzer in coordinator.analyzers.values():
        assert analyzer.reset_calls == 2
        assert len(analyzer.analyze_calls) == 2


def test_process_is_transactional_when_one_timeframe_analysis_fails() -> None:
    RecordingAnalyzer.fail_on = Timeframe.H1
    coordinator = MultiTimeframeCoordinator(
        analyzer_factory=RecordingAnalyzer,
    )

    with pytest.raises(RuntimeError, match="failed H1"):
        coordinator.process(_bars_by_timeframe())

    assert coordinator.manager.state.processed_updates == 0
    assert coordinator.manager.state.timeframe_states == {}


def test_reset_resets_every_analyzer_and_manager_state() -> None:
    coordinator = MultiTimeframeCoordinator(
        analyzer_factory=RecordingAnalyzer,
    )
    coordinator.process(_bars_by_timeframe())

    coordinator.reset()

    assert coordinator.manager.state.timeframe_states == {}
    for analyzer in coordinator.analyzers.values():
        assert analyzer.reset_calls == 2


def test_factory_must_return_a_unique_analyzer_per_timeframe() -> None:
    shared = RecordingAnalyzer()

    with pytest.raises(ValueError, match="new analyzer instance"):
        MultiTimeframeCoordinator(
            analyzer_factory=lambda: shared,
        )


def test_wrong_timeframe_state_fails_before_manager_update() -> None:
    RecordingAnalyzer.wrong_state_on = Timeframe.H4
    coordinator = MultiTimeframeCoordinator(
        analyzer_factory=RecordingAnalyzer,
    )

    with pytest.raises(ValueError, match="expected H4"):
        coordinator.process(_bars_by_timeframe())

    assert coordinator.manager.state.processed_updates == 0


def test_missing_timeframe_bars_fail_closed() -> None:
    coordinator = MultiTimeframeCoordinator(
        analyzer_factory=RecordingAnalyzer,
    )
    bars = _bars_by_timeframe()
    bars.pop(Timeframe.DAILY)

    with pytest.raises(ValueError, match="Missing bars for D1"):
        coordinator.process(bars)
