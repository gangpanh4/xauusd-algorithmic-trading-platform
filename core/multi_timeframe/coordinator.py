"""
Multi-Timeframe Coordinator.

High-level orchestrator for the complete
Multi-Timeframe subsystem.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from core.data.market_data import MarketBar

from .analyzer import TimeframeAnalyzer
from .config import MultiTimeframeConfig
from .engine import MultiTimeframeEngine
from .enums import Timeframe
from .manager import MultiTimeframeManager
from .models import MultiTimeframeResult


class MultiTimeframeCoordinator:
    """
    Coordinates the complete Multi-Timeframe workflow.

    Responsibilities
    ----------------
    1. Analyze each timeframe.
    2. Update manager state.
    3. Execute the MultiTimeframeEngine.
    4. Return one MultiTimeframeResult.
    """

    def __init__(
        self,
        config: MultiTimeframeConfig | None = None,
    ) -> None:

        self.config = config or MultiTimeframeConfig()

        self.analyzer = TimeframeAnalyzer()

        self.manager = MultiTimeframeManager(
            self.config,
        )

        self.engine = MultiTimeframeEngine(
            self.config,
        )

    def reset(
        self,
    ) -> None:
        """
        Reset the complete subsystem.
        """

        self.analyzer.reset()

        self.manager.reset()

    def process(
        self,
        bars_by_timeframe: Mapping[
            Timeframe,
            Sequence[MarketBar],
        ],
    ) -> MultiTimeframeResult:
        """
        Analyze every configured timeframe.
        """

        for timeframe in self.config.active_timeframes:

            bars = bars_by_timeframe.get(
                timeframe,
            )

            if not bars:
                raise ValueError(
                    f"Missing bars for {timeframe.value}."
                )

            state = self.analyzer.analyze(
                timeframe=timeframe,
                bars=bars,
            )

            self.manager.update(
                timeframe,
                state,
            )

        return self.engine.process(
            self.manager,
        )