"""Backtest-safe adapter for observational strategy evaluation.

This adapter consumes synchronized completed-bar multi-timeframe results and
records strategy and methodology observations without opening trades or
mutating the active trading pipeline.
"""

from __future__ import annotations

from datetime import UTC, datetime

from core.data.models import MarketBar
from core.multi_timeframe.models import MultiTimeframeResult
from core.regime_detector.models import MarketRegime

from .methodology_observer import (
    BacktestMethodologyObserver,
    MethodologyObservation,
)
from .post_expiry_trigger_tracker import (
    PostExpiryTriggerRecord,
    PostExpiryTriggerTracker,
)

from core.strategies import (
    StrategyContext,
    StrategyObservation,
    XAUUSDBOSCHOCHStrategy,
)


class BacktestStrategyObserver:
    """Run observational strategy and methodology logic on ordered M5 closes."""

    def __init__(
        self,
        strategy: XAUUSDBOSCHOCHStrategy | None = None,
        *,
        methodology_observer: BacktestMethodologyObserver | None = None,
    ) -> None:
        self.strategy = strategy or XAUUSDBOSCHOCHStrategy()
        self.methodology_observer = (
            methodology_observer or BacktestMethodologyObserver()
        )
        self._last_timestamp: datetime | None = None
        self._last_bar_index: int | None = None
        self._post_expiry_tracker = PostExpiryTriggerTracker(8)

    def reset(self) -> None:
        """Reset chronology and all owned observational lifecycle state."""

        self.strategy.reset()
        self.methodology_observer.reset()
        self._last_timestamp = None
        self._last_bar_index = None
        self._post_expiry_tracker.reset()

    def observe(
        self,
        *,
        multi_timeframe: MultiTimeframeResult,
        current_bar: MarketBar,
        current_bar_index: int,
        market_regime: MarketRegime | None = None,
    ) -> StrategyObservation:
        """Observe one completed M5 bar using synchronized market facts.

        Duplicate or decreasing timestamps and bar indexes are rejected. When a
        regime is supplied, its observation timestamp must match this completed
        candle exactly; stale and future regime facts are rejected.

        SMC and ICT methodology results are evaluated and stored as research-only
        diagnostics. They are not passed to the baseline strategy and do not
        authorize candidates, signals, risk, orders, or execution.
        """

        if not isinstance(multi_timeframe, MultiTimeframeResult):
            raise TypeError("multi_timeframe must be MultiTimeframeResult")
        if not isinstance(current_bar, MarketBar):
            raise TypeError("current_bar must be MarketBar")
        if isinstance(current_bar_index, bool) or not isinstance(
            current_bar_index,
            int,
        ):
            raise TypeError("current_bar_index must be an integer")
        if current_bar_index < 0:
            raise ValueError("current_bar_index cannot be negative")
        if market_regime is not None and not isinstance(
            market_regime,
            MarketRegime,
        ):
            raise TypeError("market_regime must be MarketRegime or None")

        timestamp = current_bar.timestamp.astimezone(UTC)
        if market_regime is not None:
            regime_timestamp = market_regime.observation_timestamp
            if (
                regime_timestamp.tzinfo is None
                or regime_timestamp.utcoffset() is None
            ):
                raise ValueError(
                    "market_regime observation_timestamp must be timezone-aware"
                )
            if regime_timestamp.astimezone(UTC) != timestamp:
                raise ValueError(
                    "market_regime observation_timestamp must match "
                    "current_bar timestamp"
                )

        if self._last_timestamp is not None and timestamp <= self._last_timestamp:
            raise ValueError(
                "strategy observation timestamps must be strictly increasing"
            )
        if (
            self._last_bar_index is not None
            and current_bar_index <= self._last_bar_index
        ):
            raise ValueError(
                "strategy observation bar indexes must be strictly increasing"
            )

        context = StrategyContext(
            multi_timeframe=multi_timeframe,
            current_bar=current_bar,
            current_bar_index=current_bar_index,
            market_regime=market_regime,
        )
        self.methodology_observer.observe(context)
        self._post_expiry_tracker.observe(
            strategy=self.strategy,
            context=context,
        )
        observation = self.strategy.observe(context)
        if (
            observation.reason_code == "EXPIRED"
            and observation.setup is not None
        ):
            self._post_expiry_tracker.register(
                observation.setup,
                expired_at=observation.timestamp,
            )
        self._last_timestamp = timestamp
        self._last_bar_index = current_bar_index
        return observation

    @property
    def observations(self) -> tuple[StrategyObservation, ...]:
        """Return immutable chronological strategy observations."""

        return tuple(self.strategy.state.observations)

    def observation_summary(self) -> dict[str, int]:
        """Return counts grouped by strategy reason code."""

        return self.strategy.state.observation_summary()

    @property
    def methodology_observations(
        self,
    ) -> tuple[MethodologyObservation, ...]:
        """Return immutable SMC and ICT diagnostic history."""

        return self.methodology_observer.observations

    def methodology_summary(self) -> dict[str, int]:
        """Return methodology counts without affecting strategy state."""

        return self.methodology_observer.summary()

    @property
    def post_expiry_triggers(
        self,
    ) -> tuple[PostExpiryTriggerRecord, ...]:
        return self._post_expiry_tracker.records

    @property
    def candidate_count(self) -> int:
        """Return candidate count without affecting executed trades."""

        return sum(
            observation.candidate_trade is not None
            for observation in self.strategy.state.observations
        )
