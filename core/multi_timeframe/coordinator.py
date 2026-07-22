"""
Multi-Timeframe Coordinator.

High-level orchestrator for the complete
Multi-Timeframe subsystem.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType

from core.data.models import MarketBar

from .analyzer import TimeframeAnalyzer
from .config import MultiTimeframeConfig
from .engine import MultiTimeframeEngine
from .enums import Timeframe
from .manager import MultiTimeframeManager
from .models import MultiTimeframeResult, TimeframeState


class MultiTimeframeCoordinator:
    """
    Coordinates the complete Multi-Timeframe workflow.

    Responsibilities
    ----------------
    1. Own one isolated stateful analyzer per timeframe.
    2. Analyze each configured timeframe as one complete snapshot.
    3. Update manager state transactionally.
    4. Execute the MultiTimeframeEngine.
    5. Return one MultiTimeframeResult.

    ``TimeframeAnalyzer.analyze()`` receives the complete supplied snapshot but
    owns incremental state for its timeframe. Unchanged snapshots reuse cached
    states; compatible forward snapshots process only newly completed bars; and
    incompatible historical revisions trigger a controlled analyzer rebuild.
    """

    def __init__(
        self,
        config: MultiTimeframeConfig | None = None,
        *,
        analyzer_factory: Callable[[], TimeframeAnalyzer] | None = None,
    ) -> None:
        self.config = config or MultiTimeframeConfig()
        self._validate_configured_timeframes()

        factory = analyzer_factory or TimeframeAnalyzer
        self._analyzers: dict[Timeframe, TimeframeAnalyzer] = {
            timeframe: factory()
            for timeframe in self.config.active_timeframes
        }

        if len({id(analyzer) for analyzer in self._analyzers.values()}) != len(
            self._analyzers
        ):
            raise ValueError(
                "analyzer_factory must return a new analyzer instance for each "
                "active timeframe."
            )

        # Backward-compatible alias for callers that inspected ``analyzer``.
        # It points to the configured entry-timeframe analyzer when possible,
        # but coordinator processing always uses the isolated mapping.
        legacy_timeframe = (
            self.config.entry_timeframe
            if self.config.entry_timeframe in self._analyzers
            else self.config.active_timeframes[0]
        )
        self.analyzer = self._analyzers[legacy_timeframe]

        self.manager = MultiTimeframeManager(self.config)
        self.engine = MultiTimeframeEngine(self.config)

        # Cache the exact immutable input snapshot and resulting state for each
        # timeframe. Higher-timeframe windows often remain unchanged across
        # many lower-timeframe observations; replaying those windows would be
        # deterministic but unnecessarily expensive.
        self._snapshot_cache: dict[
            Timeframe, tuple[tuple[MarketBar, ...], TimeframeState]
        ] = {}

    @property
    def analyzers(self) -> Mapping[Timeframe, TimeframeAnalyzer]:
        """Return a read-only mapping of isolated timeframe analyzers."""

        return MappingProxyType(self._analyzers)

    def get_analyzer(self, timeframe: Timeframe) -> TimeframeAnalyzer:
        """Return the isolated analyzer owned by ``timeframe``."""

        if not isinstance(timeframe, Timeframe):
            raise TypeError("timeframe must be a Timeframe")

        try:
            return self._analyzers[timeframe]
        except KeyError as exc:
            raise ValueError(
                f"Timeframe {timeframe.value} is not active in this coordinator."
            ) from exc

    def reset(self) -> None:
        """Reset every isolated analyzer and all aggregate manager state."""

        for analyzer in self._analyzers.values():
            analyzer.reset()

        self.manager.reset()
        self._snapshot_cache.clear()

    def process(
        self,
        bars_by_timeframe: Mapping[Timeframe, Sequence[MarketBar]],
    ) -> MultiTimeframeResult:
        """Analyze one complete synchronized snapshot of all active timeframes.

        Analysis is transactional: manager state is updated only after every
        timeframe has been analyzed successfully. A failure in one timeframe
        therefore cannot leave a partially refreshed multi-timeframe result.
        """

        if not isinstance(bars_by_timeframe, Mapping):
            raise TypeError("bars_by_timeframe must be a mapping")

        pending_states: dict[Timeframe, TimeframeState] = {}
        pending_cache: dict[
            Timeframe, tuple[tuple[MarketBar, ...], TimeframeState]
        ] = {}

        for timeframe in self.config.active_timeframes:
            bars = bars_by_timeframe.get(timeframe)

            if not bars:
                raise ValueError(f"Missing bars for {timeframe.value}.")

            immutable_bars = tuple(bars)
            cached = self._snapshot_cache.get(timeframe)

            if cached is not None and cached[0] == immutable_bars:
                state = cached[1]
            else:
                analyzer = self._analyzers[timeframe]

                if cached is None:
                    analyzer.reset()

                # The analyzer owns incremental streaming state for its
                # timeframe. It decides whether the supplied snapshot can be
                # appended safely or requires a controlled rebuild.
                state = analyzer.analyze(
                    timeframe=timeframe,
                    bars=immutable_bars,
                )

                if state.timeframe is not timeframe:
                    raise ValueError(
                        "TimeframeAnalyzer returned a state for "
                        f"{state.timeframe.value}; expected {timeframe.value}."
                    )

            pending_states[timeframe] = state
            pending_cache[timeframe] = (immutable_bars, state)

        for timeframe in self.config.active_timeframes:
            self.manager.update(
                timeframe,
                pending_states[timeframe],
            )

        result = self.engine.process(self.manager)

        # Publish the cache only after every analysis, manager update, and
        # aggregate calculation has completed successfully.
        self._snapshot_cache = pending_cache
        return result

    def _validate_configured_timeframes(self) -> None:
        """Validate the timeframe ownership contract used by the coordinator."""

        active = self.config.active_timeframes

        if not active:
            raise ValueError("active_timeframes must not be empty")

        if len(set(active)) != len(active):
            raise ValueError("active_timeframes must not contain duplicates")

        missing_from_hierarchy = [
            timeframe
            for timeframe in active
            if timeframe not in self.config.hierarchy
        ]
        if missing_from_hierarchy:
            labels = ", ".join(
                timeframe.value for timeframe in missing_from_hierarchy
            )
            raise ValueError(
                "Every active timeframe must appear in hierarchy; missing: "
                f"{labels}."
            )
