"""Historical backtesting engine orchestration."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from math import isfinite
from time import perf_counter

from core.data.models import MarketBar as SharedMarketBar
from core.execution_economics.models import ExecutionEconomicsProfile
from core.feature_engineering.models import FeatureVector
from core.market_structure.models import MarketStructureResult
from core.multi_timeframe.enums import Timeframe
from core.multi_timeframe.history_alignment import completed_period_buckets
from core.multi_timeframe.models import MultiTimeframeResult
from core.regime_detector.models import MarketBar, MarketRegime
from core.research_analytics.engine import ResearchAnalyticsEngine
from core.research_analytics.models import TradeAnalytics
from core.research_analytics.report_builder import ResearchReportBuilder
from core.research_analytics.storage import ResearchStorage
from core.risk_manager.config import LotSizingMode as RiskLotSizingMode
from core.risk_manager.models import RiskDecision
from core.signal_generator.models import SignalDirection
from core.strategies import StrategyObservation
from core.trading_pipeline.market_context import MarketContext
from core.trading_pipeline.models import (
    PipelineObservationAudit,
    PipelineResult,
)
from core.trading_pipeline.pipeline import TradingPipeline

from .candidate_outcome_models import CandidateOutcomeEvaluation
from .candidate_outcome_tracker import CandidateOutcomeTracker
from .config import BacktestConfig
from .methodology_observer import MethodologyObservation
from .models import (
    BacktestReplayContext,
    BacktestResult,
    BacktestTrade,
)
from .run_output import BacktestRunOutput
from .simulator import IncrementalTradeSimulation, TradeSimulator
from .state import BacktestState
from .strategy_comparison import (
    BacktestStrategyComparison,
    BacktestStrategyComparisonBuilder,
)
from .strategy_observer import BacktestStrategyObserver


class BacktestingEngine:
    """Execute a deterministic, single-position historical backtest.

    The production path advances one pending/open simulation with exactly one
    completed historical bar at a time. No future-bar slice is passed to the
    default :class:`TradeSimulator`. A legacy compatibility path remains only
    for injected custom simulators that implement ``simulate`` but not the
    incremental ``begin`` / ``process_bar`` contract.
    """

    DEFAULT_STOP_LOSS_DISTANCE = 2.5
    DEFAULT_TICK_SIZE = 0.01
    DEFAULT_TICK_VALUE_PER_LOT = 1.0
    DEFAULT_LOT_STEP = 0.01

    def __init__(
        self,
        config: BacktestConfig,
        *,
        stop_loss_distance: float = DEFAULT_STOP_LOSS_DISTANCE,
        tick_size: float = DEFAULT_TICK_SIZE,
        tick_value_per_lot: float = DEFAULT_TICK_VALUE_PER_LOT,
        lot_step: float = DEFAULT_LOT_STEP,
        execution_profile: ExecutionEconomicsProfile | None = None,
        progress_interval_bars: int | None = 1_000,
        multi_timeframe_window_bars: int = 500,
    ) -> None:
        self.config = config
        if execution_profile is None and config.execution_profile is not None:
            execution_profile = config.execution_profile
        if execution_profile is not None and not isinstance(
            execution_profile,
            ExecutionEconomicsProfile,
        ):
            raise TypeError(
                "execution_profile must be an ExecutionEconomicsProfile"
            )
        self.execution_profile = execution_profile
        instrument = (
            execution_profile.instrument
            if execution_profile is not None
            else None
        )
        self.stop_loss_distance = self._require_positive_finite(
            (
                instrument.minimum_stop_distance
                if instrument is not None
                else stop_loss_distance
            ),
            "stop_loss_distance",
        )
        self.tick_size = self._require_positive_finite(
            instrument.tick_size if instrument is not None else tick_size,
            "tick_size",
        )
        self.tick_value_per_lot = self._require_positive_finite(
            (
                instrument.tick_value_per_lot
                if instrument is not None
                else tick_value_per_lot
            ),
            "tick_value_per_lot",
        )
        self.lot_step = self._require_positive_finite(
            instrument.volume_step if instrument is not None else lot_step,
            "lot_step",
        )
        self.progress_interval_bars = self._validate_progress_interval(
            progress_interval_bars
        )
        self.multi_timeframe_window_bars = self._validate_mtf_window(
            multi_timeframe_window_bars
        )

        self.state = BacktestState()
        costs = execution_profile.costs if execution_profile is not None else None
        self.simulator = TradeSimulator(
            tick_size=self.tick_size,
            tick_value_per_lot=self.tick_value_per_lot,
            spread_points=(
                costs.spread_points
                if costs is not None
                else self.config.spread_points
            ),
            slippage_points=(
                costs.slippage_points
                if costs is not None
                else self.config.slippage_points
            ),
            commission_per_trade=(
                costs.commission_per_trade
                if costs is not None
                else self.config.commission_per_trade
            ),
            commission_per_lot=(
                costs.commission_per_lot
                if costs is not None
                else self.config.commission_per_lot
            ),
            execution_profile=execution_profile,
        )
        self.pipeline = self._create_pipeline()
        self.strategy_observer = BacktestStrategyObserver()
        self.candidate_outcome_tracker = CandidateOutcomeTracker()
        self.research_storage = ResearchStorage()
        self.research_engine = ResearchAnalyticsEngine(self.research_storage)
        self._pending_analytics: TradeAnalytics | None = None
        self._active_simulation: IncrementalTradeSimulation | None = None
        self._active_pipeline_result: PipelineResult | None = None
        self._active_observation_bar: MarketBar | None = None
        self._position_registered = False
        self._observation_audits: list[PipelineObservationAudit] = []
        self._last_pipeline_observation_timestamp: datetime | None = None
        self._last_strategy_m5_end = 0
        self._progress_started_at: float | None = None
        self._mtf_cache_context_id: int | None = None
        self._mtf_close_times: dict[str, tuple[datetime, ...]] = {}
        self._mtf_shared_bars: dict[str, tuple[SharedMarketBar, ...]] = {}
        self._derived_cache: dict[
            int,
            tuple[
                tuple[SharedMarketBar, ...],
                tuple[SharedMarketBar, ...],
            ],
        ] = {}

    def reset(self) -> None:
        """Reset all mutable state, including analytical and research engines."""

        self.state.reset()
        self.pipeline = self._create_pipeline()
        self.strategy_observer.reset()
        self._get_candidate_outcome_tracker().reset()
        self.research_storage = ResearchStorage()
        self.research_engine = ResearchAnalyticsEngine(self.research_storage)
        self._pending_analytics = None
        self._active_simulation = None
        self._active_pipeline_result = None
        self._active_observation_bar = None
        self._position_registered = False
        self._observation_audits = []
        self._last_pipeline_observation_timestamp = None
        self._last_strategy_m5_end = 0
        self._progress_started_at = None
        self._mtf_cache_context_id = None
        self._mtf_close_times = {}
        self._mtf_shared_bars = {}
        self._derived_cache = {}

    @property
    def observation_audits(self) -> tuple[PipelineObservationAudit, ...]:
        """Return immutable audit records for processed observations."""

        return tuple(self._observation_audits)

    def observation_audit_summary(self) -> dict[str, int]:
        """Return deterministic counts grouped by final audit reason code."""

        summary: dict[str, int] = {}
        for audit in self._observation_audits:
            key = audit.reason_code or "APPROVED"
            summary[key] = summary.get(key, 0) + 1
        return dict(sorted(summary.items()))

    @property
    def strategy_observations(self) -> tuple[StrategyObservation, ...]:
        """Return immutable observational-strategy history."""

        return self.strategy_observer.observations

    def strategy_observation_summary(self) -> dict[str, int]:
        """Return observational strategy counts grouped by reason code."""

        return self.strategy_observer.observation_summary()

    @property
    def methodology_observations(
        self,
    ) -> tuple[MethodologyObservation, ...]:
        """Return immutable SMC and ICT methodology diagnostic history."""

        return self.strategy_observer.methodology_observations

    def methodology_summary(self) -> dict[str, int]:
        """Return methodology counts without changing strategy or trade state."""

        return self.strategy_observer.methodology_summary()

    @property
    def strategy_candidate_count(self) -> int:
        """Return candidate count without affecting executed trades."""

        return self.strategy_observer.candidate_count

    def _get_candidate_outcome_tracker(
        self,
    ) -> CandidateOutcomeTracker:
        """Return the tracker, creating it for partially constructed engines.

        Some focused tests and legacy integrations construct the engine with
        ``object.__new__`` and intentionally bypass ``__init__``. Lazy creation
        preserves those lightweight fixtures without weakening normal runtime
        initialization.
        """

        tracker = getattr(self, "candidate_outcome_tracker", None)
        if tracker is None:
            tracker = CandidateOutcomeTracker()
            self.candidate_outcome_tracker = tracker
        return tracker

    @property
    def candidate_outcome_evaluations(
        self,
    ) -> tuple[CandidateOutcomeEvaluation, ...]:
        """Return immutable finalized observational candidate outcomes."""

        return self._get_candidate_outcome_tracker().evaluations

    def candidate_outcome_summary(self) -> dict[str, int]:
        """Return deterministic counts grouped by candidate outcome."""

        return self._get_candidate_outcome_tracker().summary()

    def build_strategy_comparison(
        self,
        backtest_result: BacktestResult,
    ) -> BacktestStrategyComparison:
        """Build a read-only pipeline-versus-strategy comparison report.

        The report consumes completed backtest output and already-recorded audit
        histories. It does not process bars, create candidates, change risk,
        or authorize execution.
        """

        return BacktestStrategyComparisonBuilder.build(
            backtest_result=backtest_result,
            pipeline_audits=self.observation_audits,
            strategy_observations=self.strategy_observations,
            post_expiry_triggers=getattr(
                self.strategy_observer,
                'post_expiry_triggers',
                (),
            ),
        )

    def run_with_strategy_comparison(
        self,
        context: MarketContext,
    ) -> BacktestRunOutput:
        """Execute one backtest and return result plus comparison together.

        This is an additive entry point. The existing ``run`` method and its
        ``BacktestResult`` return type remain unchanged for all current callers.
        """

        result = self.run(context)
        return BacktestRunOutput(
            result=result,
            strategy_comparison=self.build_strategy_comparison(result),
            candidate_outcome_evaluations=(
                self.candidate_outcome_evaluations
            ),
            candidate_outcome_summary=self.candidate_outcome_summary(),
        )

    def run(self, context: MarketContext) -> BacktestResult:
        """Execute M5 decisions while retaining completed-M15 simulation."""

        decision_bars = self._prepare_historical_bars(context)
        simulation_bars = self._prepare_simulation_bars(context)
        self._initialize(decision_bars)
        total_bars = len(decision_bars)
        self._progress_started_at = perf_counter()
        self._prepare_mtf_runtime_cache(context)
        simulation_index = 0
        complete_snapshot_count = 0
        replay_window = (
            context.replay_window
            if isinstance(context, BacktestReplayContext)
            else None
        )

        for index, bar in enumerate(decision_bars):
            boundary = bar.timestamp.astimezone(UTC) + timedelta(minutes=5)
            while simulation_index < len(simulation_bars):
                simulation_bar = simulation_bars[simulation_index]
                simulation_close = (
                    simulation_bar.timestamp.astimezone(UTC)
                    + timedelta(minutes=15)
                )
                if simulation_close > boundary:
                    break
                if self._supports_incremental_simulator():
                    self._advance_incremental_trade(simulation_bar)
                else:
                    self._settle_active_trade_if_due(simulation_bar.timestamp)
                simulation_index += 1

            self.state.processed_bar_count += 1

            if self._maximum_trades_reached() and not self._has_active_position():
                self._report_progress(index=index, total_bars=total_bars, force=True)
                break

            result, observation_bar = self._process_observation(
                context=context,
                m5_index=index,
                m5_bar=bar,
            )
            if result is None:
                # Incomplete synchronized history is warm-up-only absence. It
                # never downgrades the analytical clock to another timeframe.
                self._report_progress(index=index, total_bars=total_bars)
                continue

            self._collect_observation_audit(observation_bar)

            if self.config.debug_logging and index < 20:
                self._print_debug_result(index=index, result=result)

            self._report_progress(index=index, total_bars=total_bars)

            eligible = (
                observation_bar.timestamp.astimezone(UTC)
                >= replay_window.first_eligible_m5_timestamp
                if replay_window is not None
                else complete_snapshot_count >= self.config.warmup_bars
            )
            complete_snapshot_count += 1
            if not eligible:
                continue

            # Continue feeding every completed bar through analytical engines
            # while exposure is pending/open, but never create a second trade.
            if self._has_active_position():
                continue

            if not self._direction_is_enabled(result):
                continue

            future_simulation_bars = [
                value
                for value in simulation_bars
                if value.timestamp.astimezone(UTC)
                > observation_bar.timestamp.astimezone(UTC)
            ]
            if not future_simulation_bars:
                continue

            if self._supports_incremental_simulator():
                self._begin_incremental_trade(
                    result=result,
                    observation_bar=observation_bar,
                )
            else:
                # Compatibility only for injected legacy simulators used by
                # existing integrations and tests. The default simulator never
                # receives or scans this future slice.
                self._record_trade(
                    result=result,
                    entry_bar=observation_bar,
                    future_bars=future_simulation_bars,
                )

        self._get_candidate_outcome_tracker().finalize()
        return self._finalize()


    def _process_observation(
        self,
        *,
        context: MarketContext,
        m5_index: int,
        m5_bar: MarketBar,
    ) -> tuple[PipelineResult | None, MarketBar]:
        """Process one completed M5 observation with no-lookahead confluence.

        The default production pipeline receives synchronized M5/M15/H1/H4
        histories plus completed D1/W1 aggregates. Injected test pipelines
        without MTF components remain supported, but they also receive M5;
        M15 is never substituted as an analytical observation.
        """

        del m5_index

        if not self._supports_multi_timeframe_pipeline():
            return (
                self._process_pipeline_bar(
                    m5_bar,
                    account_balance=self.state.current_equity,
                    stop_loss_distance=self.stop_loss_distance,
                    pip_value=self.tick_value_per_lot,
                    tick_size=self.tick_size,
                    lot_step=self.lot_step,
                ),
                m5_bar,
            )

        boundary = m5_bar.timestamp.astimezone(UTC) + timedelta(minutes=5)
        self._ensure_mtf_runtime_cache(context)

        m5_end = self._visible_end("m5", boundary)
        if (
            m5_end == 0
            or context.m5_bars[m5_end - 1].timestamp.astimezone(UTC)
            != m5_bar.timestamp.astimezone(UTC)
        ):
            return None, m5_bar
        snapshot = self._strategy_mtf_snapshot(
            boundary=boundary,
            m5_end=m5_end,
        )
        if snapshot is None:
            return None, m5_bar

        mtf_result = self.pipeline.multi_timeframe.process(snapshot)
        confluence = self.pipeline.confluence_engine.evaluate_multi_timeframe(
            mtf_result
        )
        result = self._process_pipeline_bar(
            m5_bar,
            confluence=confluence,
            multi_timeframe_result=mtf_result,
            market_structure_result=mtf_result.m5.market_structure,
            account_balance=self.state.current_equity,
            stop_loss_distance=self.stop_loss_distance,
            pip_value=self.tick_value_per_lot,
            tick_size=self.tick_size,
            lot_step=self.lot_step,
        )
        self._complete_latest_strategy_observation(
            multi_timeframe=mtf_result,
            observation_bar=m5_bar,
            pipeline_result=result,
            visible_m5_end=m5_end,
        )
        return result, m5_bar


    def _observe_new_strategy_m5_bars(
        self,
        *,
        context: MarketContext,
        visible_m5_end: int,
    ) -> MultiTimeframeResult:
        """Observe every newly completed M5 bar exactly once."""

        if visible_m5_end <= 0:
            raise ValueError("visible_m5_end must be greater than zero")

        previous_end = getattr(self, "_last_strategy_m5_end", 0)
        if previous_end < 0:
            raise ValueError("_last_strategy_m5_end cannot be negative")
        if previous_end > visible_m5_end:
            raise ValueError(
                "visible M5 history moved backwards during strategy replay"
            )

        final_result: MultiTimeframeResult | None = None

        for m5_end in range(previous_end + 1, visible_m5_end + 1):
            boundary = self._mtf_close_times["m5"][m5_end - 1]
            snapshot = self._strategy_mtf_snapshot(
                boundary=boundary,
                m5_end=m5_end,
            )

            if snapshot is None:
                self._last_strategy_m5_end = m5_end
                continue

            final_result = self.pipeline.multi_timeframe.process(snapshot)
            if m5_end < visible_m5_end:
                self._observe_strategy(
                    multi_timeframe=final_result,
                    observation_bar=context.m5_bars[m5_end - 1],
                )
                self._last_strategy_m5_end = m5_end

        if final_result is not None:
            return final_result

        boundary = self._mtf_close_times["m5"][visible_m5_end - 1]
        snapshot = self._strategy_mtf_snapshot(
            boundary=boundary,
            m5_end=visible_m5_end,
        )
        if snapshot is None:
            raise RuntimeError(
                "final visible M5 bar lacks a complete multi-timeframe snapshot"
            )

        return self.pipeline.multi_timeframe.process(snapshot)

    def _strategy_mtf_snapshot(
        self,
        *,
        boundary: datetime,
        m5_end: int,
    ) -> Mapping[Timeframe, tuple[SharedMarketBar, ...]] | None:
        """Build one no-lookahead snapshot at an exact completed M5 close."""

        m15_end = self._visible_end("m15", boundary)
        h1_end = self._visible_end("h1", boundary)
        h4_end = self._visible_end("h4", boundary)
        base = {
            Timeframe.H4: self._window("h4", h4_end),
            Timeframe.H1: self._window("h1", h1_end),
            Timeframe.M15: self._window("m15", m15_end),
            Timeframe.M5: self._window("m5", m5_end),
        }
        if any(
            len(values) < self.multi_timeframe_window_bars
            for values in base.values()
        ):
            return None

        daily, weekly = self._derived_windows(
            h4_end=h4_end,
            boundary=boundary,
        )
        if not daily or not weekly:
            return None

        return {
            Timeframe.WEEKLY: weekly,
            Timeframe.DAILY: daily,
            **base,
        }

    def _observe_strategy(
        self,
        *,
        multi_timeframe: MultiTimeframeResult,
        observation_bar: MarketBar,
        market_regime: MarketRegime | None = None,
    ) -> StrategyObservation | None:
        """Record one synchronized strategy observation without execution.

        The M5 structure engine owns the authoritative confirmation index. The
        strategy must use that index rather than the outer M15 loop index or an
        independently calculated absolute index, otherwise trigger confirmation
        timing could diverge from the market-structure evidence.
        """

        market_structure = multi_timeframe.m5.market_structure
        if not isinstance(market_structure, MarketStructureResult):
            return None
        structure_state = market_structure.structure_state
        if structure_state is None:
            return None

        shared_bar = self._to_shared_bar(observation_bar)
        tracker = self._get_candidate_outcome_tracker()
        tracker.process_bar(shared_bar)
        observation = self.strategy_observer.observe(
            multi_timeframe=multi_timeframe,
            current_bar=shared_bar,
            current_bar_index=structure_state.current_bar_index,
            market_regime=market_regime,
        )
        if observation.candidate_trade is not None:
            tracker.register(observation.candidate_trade)
        return observation

    def _complete_latest_strategy_observation(
        self,
        *,
        multi_timeframe: MultiTimeframeResult,
        observation_bar: MarketBar,
        pipeline_result: PipelineResult | None,
        visible_m5_end: int,
    ) -> StrategyObservation | None:
        """Observe the latest M5 candle after its one pipeline evaluation.

        Earlier newly visible M5 candles are replayed observationally without a
        regime because the production pipeline does not process those candles.
        The latest candle is deferred until ``PipelineResult`` exists so the
        exact same-candle ``MarketRegime`` can be supplied without a second
        detector update or stale-state reuse.
        """

        if pipeline_result is None:
            return None
        if isinstance(visible_m5_end, bool) or not isinstance(
            visible_m5_end,
            int,
        ):
            raise TypeError("visible_m5_end must be an integer")
        if visible_m5_end <= 0:
            raise ValueError("visible_m5_end must be greater than zero")

        observation = self._observe_strategy(
            multi_timeframe=multi_timeframe,
            observation_bar=observation_bar,
            market_regime=getattr(pipeline_result, "regime", None),
        )
        self._last_strategy_m5_end = visible_m5_end
        return observation

    def _process_pipeline_bar(
        self,
        bar: MarketBar,
        **kwargs: object,
    ) -> PipelineResult | None:
        """Process one unique, chronologically increasing analytical bar.

        M5 is the canonical analytical clock. Exact duplicates are skipped to
        protect stateful engines, while decreasing timestamps remain a hard
        chronology error.
        """

        timestamp = bar.timestamp.astimezone(UTC)
        previous = self._last_pipeline_observation_timestamp
        if previous is not None:
            if timestamp == previous:
                return None
            if timestamp < previous:
                raise ValueError(
                    "pipeline observation timestamps must be strictly increasing"
                )

        result = self.pipeline.process_bar(bar, **kwargs)
        self._last_pipeline_observation_timestamp = timestamp
        return result


    def _collect_observation_audit(self, observation_bar: MarketBar) -> None:
        """Collect the pipeline audit emitted for one completed observation.

        The production :class:`TradingPipeline` must emit exactly one audit for
        every successful ``process_bar`` call. Legacy injected test pipelines
        that do not expose the audit contract remain compatible and are simply
        ignored.
        """

        if not hasattr(self.pipeline, "last_observation_audit"):
            return

        audit = self.pipeline.last_observation_audit
        if audit is None:
            raise RuntimeError(
                "pipeline did not emit an observation audit after process_bar"
            )
        if not isinstance(audit, PipelineObservationAudit):
            raise TypeError(
                "pipeline last_observation_audit must be "
                "PipelineObservationAudit"
            )

        expected_timestamp = observation_bar.timestamp.astimezone(UTC)
        if audit.timestamp != expected_timestamp:
            raise ValueError(
                "pipeline observation audit timestamp does not match the "
                "processed observation bar"
            )

        if self._observation_audits:
            previous = self._observation_audits[-1]
            if audit.timestamp <= previous.timestamp:
                raise ValueError(
                    "pipeline observation audit timestamps must be strictly "
                    "increasing"
                )

        self._observation_audits.append(audit)

    def _supports_multi_timeframe_pipeline(self) -> bool:
        return (
            hasattr(self.pipeline, "multi_timeframe")
            and hasattr(self.pipeline, "confluence_engine")
            and callable(getattr(self.pipeline, "process_bar", None))
        )


    def _prepare_mtf_runtime_cache(self, context: MarketContext) -> None:
        """Precompute immutable MTF lookup data for one backtest context.

        The prior implementation rescanned every timeframe history, rebuilt
        D1/W1 candles, and reconverted rolling bars on every M15 observation.
        This cache preserves the exact completed-bar semantics while replacing
        those repeated full-history operations with binary-search lookups and
        tuple slicing.
        """

        self._mtf_cache_context_id = id(context)
        durations = {
            "m5": timedelta(minutes=5),
            "m15": timedelta(minutes=15),
            "h1": timedelta(hours=1),
            "h4": timedelta(hours=4),
        }
        source = {
            "m5": context.m5_bars,
            "m15": context.m15_bars,
            "h1": context.h1_bars,
            "h4": context.h4_bars,
        }

        self._mtf_close_times = {
            key: tuple(
                bar.timestamp.astimezone(UTC) + durations[key]
                for bar in bars
            )
            for key, bars in source.items()
        }
        self._mtf_shared_bars = {
            key: tuple(self._to_shared_bar(bar) for bar in bars)
            for key, bars in source.items()
        }
        self._derived_cache = {}

    def _ensure_mtf_runtime_cache(self, context: MarketContext) -> None:
        if self._mtf_cache_context_id != id(context):
            self._prepare_mtf_runtime_cache(context)

    def _visible_end(self, key: str, boundary: datetime) -> int:
        return bisect_right(self._mtf_close_times[key], boundary)

    def _window(self, key: str, end: int) -> tuple[SharedMarketBar, ...]:
        start = max(0, end - self.multi_timeframe_window_bars)
        return self._mtf_shared_bars[key][start:end]

    @staticmethod
    def _visible_bars(
        bars: Sequence[MarketBar],
        boundary: datetime,
        duration: timedelta,
    ) -> list[MarketBar]:
        return [
            bar
            for bar in bars
            if bar.timestamp.astimezone(UTC) + duration <= boundary
        ]

    @classmethod
    def _aggregate_completed_bars(
        cls,
        bars: Sequence[MarketBar | SharedMarketBar],
        *,
        boundary: datetime,
        weekly: bool,
    ) -> list[SharedMarketBar]:
        return [
                SharedMarketBar(
                    timestamp=start,
                    open=float(values[0].open),
                    high=max(float(bar.high) for bar in values),
                    low=min(float(bar.low) for bar in values),
                    close=float(values[-1].close),
                    tick_volume=sum(
                        int(
                            getattr(bar, "tick_volume", 0)
                            or getattr(bar, "volume", 0)
                            or 0
                        )
                        for bar in values
                    ),
                )
            for start, values in completed_period_buckets(
                bars,
                boundary=boundary,
                weekly=weekly,
            )
        ]

    def _derived_windows(
        self,
        *,
        h4_end: int,
        boundary: datetime,
    ) -> tuple[
        tuple[SharedMarketBar, ...],
        tuple[SharedMarketBar, ...],
    ]:
        cached = self._derived_cache.get(h4_end)
        if cached is not None:
            return cached

        h4_values = self._window("h4", h4_end)
        daily = tuple(
            self._aggregate_completed_bars(
                h4_values,
                boundary=boundary,
                weekly=False,
            )
        )
        weekly = tuple(
            self._aggregate_completed_bars(
                h4_values,
                boundary=boundary,
                weekly=True,
            )
        )
        result = (daily, weekly)
        self._derived_cache[h4_end] = result
        return result

    @staticmethod
    def _to_shared_bar(bar: MarketBar) -> SharedMarketBar:
        return SharedMarketBar(
            timestamp=bar.timestamp.astimezone(UTC),
            open=float(bar.open),
            high=float(bar.high),
            low=float(bar.low),
            close=float(bar.close),
            tick_volume=int(bar.tick_volume or bar.volume or 0),
        )

    def _record_trade(
        self,
        result: PipelineResult,
        entry_bar: MarketBar,
        future_bars: list[MarketBar],
    ) -> None:
        """Compatibility path for injected batch-only simulators.

        The production engine uses :meth:`_begin_incremental_trade` instead.
        This method remains to preserve existing integrations and tests that
        replace ``engine.simulator`` with a custom ``simulate`` implementation.
        """

        trade_plan = result.trade_plan
        if trade_plan is None or trade_plan.decision != RiskDecision.APPROVE:
            return
        if not future_bars:
            return

        trade = self.simulator.simulate(
            trade_plan=trade_plan,
            entry_bar=entry_bar,
            future_bars=future_bars,
        )
        self._attach_pipeline_metadata(
            trade=trade,
            result=result,
            observation_bar=entry_bar,
        )
        self._pending_analytics = self._build_trade_analytics(
            result=result,
            observation_bar=entry_bar,
            trade=trade,
        )

        self.pipeline.register_position_opened()
        self.state.active_trade = trade
        self.state.executed_trade_count += 1

    def _supports_incremental_simulator(self) -> bool:
        return all(
            callable(getattr(self.simulator, name, None))
            for name in ("begin", "process_bar", "finalize_at_end_of_data")
        )

    def _has_active_position(self) -> bool:
        return (
            self._active_simulation is not None
            or self.state.active_trade is not None
        )

    def _begin_incremental_trade(
        self,
        *,
        result: PipelineResult,
        observation_bar: MarketBar,
    ) -> None:
        trade_plan = result.trade_plan
        if trade_plan is None or trade_plan.decision != RiskDecision.APPROVE:
            return
        if self._has_active_position():
            raise RuntimeError("cannot begin a second active trade")

        self._active_simulation = self.simulator.begin(
            trade_plan,
            observation_bar,
        )
        self._active_pipeline_result = result
        self._active_observation_bar = observation_bar
        self._position_registered = False

    def _advance_incremental_trade(self, bar: MarketBar) -> None:
        simulation = self._active_simulation
        if simulation is None:
            return

        if (
            simulation.is_pending_entry
            and bar.timestamp <= simulation.observation_bar.timestamp
        ):
            # The candle opened before (or at) the M5 observation. It may only
            # have become completed later and cannot supply a post-signal fill.
            return

        was_pending = simulation.is_pending_entry
        completed = self.simulator.process_bar(simulation, bar)

        if was_pending and not simulation.is_pending_entry:
            self.pipeline.register_position_opened()
            self.state.executed_trade_count += 1
            self._position_registered = True

        if completed is not None:
            self._complete_incremental_trade(completed)

    def _complete_incremental_trade(self, trade: BacktestTrade) -> None:
        result = self._active_pipeline_result
        observation_bar = self._active_observation_bar
        if result is None or observation_bar is None:
            raise RuntimeError("active simulation is missing pipeline evidence")

        self._attach_pipeline_metadata(
            trade=trade,
            result=result,
            observation_bar=observation_bar,
        )
        self._pending_analytics = self._build_trade_analytics(
            result=result,
            observation_bar=observation_bar,
            trade=trade,
        )

        self._active_simulation = None
        self._active_pipeline_result = None
        self._active_observation_bar = None
        self._settle_trade(trade)

    def _attach_pipeline_metadata(
        self,
        *,
        trade: BacktestTrade,
        result: PipelineResult,
        observation_bar: MarketBar,
    ) -> None:
        trade.metadata.update(
            self._build_pipeline_evidence_metadata(
                result=result,
                entry_bar=observation_bar,
                exit_timestamp=trade.exit_time,
            )
        )

    def _build_trade_analytics(
        self,
        *,
        result: PipelineResult,
        observation_bar: MarketBar,
        trade: BacktestTrade,
    ) -> TradeAnalytics:
        trade_plan = result.trade_plan
        if trade_plan is None:
            raise RuntimeError("executed trade is missing its trade plan")
        direction = (
            trade_plan.signal.direction
            if trade_plan.signal is not None
            else SignalDirection.HOLD
        )
        feature_vector = result.features or FeatureVector()
        return TradeAnalytics(
            timestamp=observation_bar.timestamp,
            direction=direction,
            regime=str(trade_plan.regime),
            result=trade.outcome.name,
            profit=trade.net_profit,
            probability=float(trade_plan.probability or 0.0),
            confidence=float(trade_plan.confidence or 0.0),
            features=feature_vector,
        )

    def _build_pipeline_evidence_metadata(
        self,
        *,
        result: PipelineResult,
        entry_bar: MarketBar,
        exit_timestamp: datetime,
    ) -> dict[str, object]:
        """Capture complete pipeline evidence plus stable research columns."""

        trade_plan = getattr(result, "trade_plan", None)
        probability = getattr(result, "probability", None)
        quality = getattr(result, "trade_quality", None)
        regime = getattr(result, "regime", None)
        confluence = getattr(result, "confluence", None)
        decision = getattr(result, "decision", None)
        signal = getattr(result, "signal", None)
        if signal is None and trade_plan is not None:
            signal = trade_plan.signal
        features = getattr(result, "features", None)
        feature_values = self._feature_values(features)
        bos = getattr(result, "bos_event", None)
        choch = getattr(result, "choch_event", None)
        liquidity = getattr(result, "liquidity_event", None)
        order_block = getattr(result, "order_block", None)
        fair_value_gap = getattr(result, "fair_value_gap", None)

        metadata: dict[str, object] = {
            "observation_timestamp": self._timestamp_text(entry_bar.timestamp),
            "scheduled_exit_timestamp": self._timestamp_text(exit_timestamp),
            "tick_size": self.tick_size,
            "tick_value_per_lot": self.tick_value_per_lot,
            "lot_step": self.lot_step,
            "pipeline_snapshot": self._snapshot(result),
            "probability": self._first_attribute(
                probability, "probability", fallback=getattr(
                    trade_plan, "probability", None
                )
            ),
            "confidence": self._first_attribute(
                probability, "confidence", fallback=getattr(
                    trade_plan, "confidence", None
                )
            ),
            "probability_accepted": getattr(probability, "accepted", None),
            "probability_reasons": self._snapshot(
                getattr(probability, "reasons", None)
            ),
            "probability_evidence": self._snapshot(
                getattr(probability, "evidence", None)
            ),
            "feature_count": (
                getattr(features, "size", None)
                if features is not None
                else getattr(trade_plan, "feature_count", None)
            ),
            "evidence_count": (
                len(probability.evidence)
                if probability is not None
                else getattr(trade_plan, "evidence_count", None)
            ),
            "features": self._snapshot(features),
            "feature_values": feature_values,
            "structure_confidence": self._mapping_value(
                feature_values, "structure_confidence"
            ),
            "regime": (
                self._enum_name(regime.primary_regime)
                if regime is not None
                else getattr(trade_plan, "regime", None)
            ),
            "regime_confidence": getattr(regime, "confidence", None),
            "regime_status_flags": (
                sorted(
                    self._enum_name(flag)
                    for flag in getattr(regime, "status_flags", ())
                )
                if regime is not None
                else None
            ),
            "trade_quality_score": getattr(quality, "score", None),
            "trade_quality_confidence": getattr(quality, "confidence", None),
            "trade_quality_level": self._optional_enum_name(
                getattr(quality, "level", None)
            ),
            "trade_quality_approved": getattr(quality, "approved", None),
            "trade_quality_reasons": self._snapshot(
                getattr(quality, "reasons", None)
            ),
            "confluence_score": getattr(confluence, "score", None),
            "confluence_approved": getattr(confluence, "approved", None),
            "decision": self._optional_enum_name(
                getattr(decision, "decision", None)
            ),
            "decision_approved": getattr(decision, "approved", None),
            "signal_score": getattr(signal, "decision_score", None),
            "signal_confidence": getattr(signal, "confidence", None),
            "signal_direction": self._optional_enum_name(
                getattr(signal, "direction", None)
            ),
            "signal_strength": self._optional_enum_name(
                getattr(signal, "strength", None)
            ),
            "signal_reasons": self._snapshot(
                getattr(signal, "reasons", None)
            ),
            "strategy_id": self._strategy_id(signal),
            "bos_present": bos is not None,
            "bos_direction": self._event_enum(bos, "direction"),
            "bos_timestamp": self._event_timestamp(bos),
            "bos_break_distance": getattr(bos, "break_distance", None),
            "bos_break_atr_multiple": getattr(
                bos, "break_atr_multiple", None
            ),
            "bos_freshness": self._mapping_value(
                feature_values, "bos_freshness"
            ),
            "bos_quality": getattr(bos, "quality", None),
            "bos_strength": getattr(bos, "strength", None),
            "bos_power_score": getattr(bos, "power_score", None),
            "bos_structure_score": getattr(bos, "structure_score", None),
            "bos_age": getattr(bos, "age", None),
            "choch_present": choch is not None,
            "choch_direction": self._event_enum(choch, "direction"),
            "choch_timestamp": self._event_timestamp(choch),
            "choch_break_distance": getattr(choch, "break_distance", None),
            "choch_break_atr_multiple": getattr(
                choch, "break_atr_multiple", None
            ),
            "choch_freshness": self._mapping_value(
                feature_values, "choch_freshness"
            ),
            "choch_quality": getattr(choch, "quality", None),
            "choch_strength": getattr(choch, "strength", None),
            "choch_power_score": getattr(choch, "power_score", None),
            "choch_structure_score": getattr(choch, "structure_score", None),
            "choch_age": getattr(choch, "age", None),
            "liquidity_present": liquidity is not None,
            "liquidity_timestamp": self._event_timestamp(liquidity),
            "liquidity_side": self._liquidity_side(liquidity),
            "liquidity_sweep_distance": getattr(
                liquidity, "sweep_distance", None
            ),
            "liquidity_atr_multiple": getattr(
                liquidity, "atr_multiple", None
            ),
            "liquidity_sweep_strength": getattr(
                liquidity, "sweep_strength", None
            ),
            "liquidity_reaction_strength": getattr(
                liquidity, "reaction_strength", None
            ),
            "liquidity_reclaim_strength": getattr(
                liquidity, "reclaim_strength", None
            ),
            "liquidity_quality": getattr(liquidity, "quality", None),
            "liquidity_age": getattr(liquidity, "age", None),
            "liquidity_freshness": self._mapping_value(
                feature_values, "liquidity_freshness"
            ),
            "order_block_present": order_block is not None,
            "order_block": self._snapshot(order_block),
            "fair_value_gap_present": fair_value_gap is not None,
            "fair_value_gap": self._snapshot(fair_value_gap),
        }
        return metadata

    @staticmethod
    def _first_attribute(
        value: object | None,
        name: str,
        *,
        fallback: object | None,
    ) -> object | None:
        return getattr(value, name, fallback) if value is not None else fallback

    @staticmethod
    def _mapping_value(
        values: Mapping[str, object] | None,
        key: str,
    ) -> object | None:
        if values is None:
            return None
        return values.get(key)

    @staticmethod
    def _feature_values(features: object | None) -> dict[str, object] | None:
        if features is None:
            return None
        return {
            feature.name: feature.value
            for feature in getattr(features, "features", ())
        }

    @classmethod
    def _strategy_id(cls, signal: object | None) -> object | None:
        metadata = getattr(signal, "metadata", None)
        if not isinstance(metadata, Mapping):
            return None
        for key in ("strategy_id", "strategy", "setup_id"):
            value = metadata.get(key)
            if value not in (None, ""):
                return cls._snapshot(value)
        return None

    @classmethod
    def _event_enum(cls, event: object | None, name: str) -> str | None:
        if event is None:
            return None
        return cls._optional_enum_name(getattr(event, name, None))

    @classmethod
    def _event_timestamp(cls, event: object | None) -> str | None:
        if event is None:
            return None
        value = getattr(event, "timestamp", None)
        return cls._timestamp_text(value) if value is not None else None

    @staticmethod
    def _liquidity_side(event: object | None) -> str | None:
        if event is None:
            return None
        level = getattr(event, "liquidity_level", None)
        is_buy_side = getattr(level, "is_buy_side", None)
        if is_buy_side is None:
            return None
        return "BUY_SIDE" if is_buy_side else "SELL_SIDE"

    @classmethod
    def _snapshot(
        cls,
        value: object,
        *,
        active_ids: set[int] | None = None,
    ) -> object:
        """Convert dataclass evidence into deterministic primitive values."""

        if active_ids is None:
            active_ids = set()
        if value is None or isinstance(value, (str, bool, int, float)):
            return value
        if isinstance(value, datetime):
            return cls._timestamp_text(value)
        if isinstance(value, Enum):
            return cls._enum_name(value)

        value_id = id(value)
        if value_id in active_ids:
            return "<recursive>"

        if is_dataclass(value):
            active_ids.add(value_id)
            try:
                return {
                    field.name: cls._snapshot(
                        getattr(value, field.name),
                        active_ids=active_ids,
                    )
                    for field in fields(value)
                }
            finally:
                active_ids.remove(value_id)

        if isinstance(value, Mapping):
            active_ids.add(value_id)
            try:
                return {
                    str(key): cls._snapshot(item, active_ids=active_ids)
                    for key, item in sorted(
                        value.items(),
                        key=lambda pair: str(pair[0]),
                    )
                }
            finally:
                active_ids.remove(value_id)

        if isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            active_ids.add(value_id)
            try:
                return [
                    cls._snapshot(item, active_ids=active_ids)
                    for item in value
                ]
            finally:
                active_ids.remove(value_id)

        attributes = getattr(value, "__dict__", None)
        if isinstance(attributes, Mapping):
            return cls._snapshot(attributes, active_ids=active_ids)
        return str(value)

    @classmethod
    def _optional_enum_name(cls, value: object | None) -> str | None:
        return cls._enum_name(value) if value is not None else None

    @staticmethod
    def _enum_name(value: object) -> str:
        name = getattr(value, "name", None)
        return str(name if name is not None else value)

    @staticmethod
    def _timestamp_text(value: object) -> str:
        if not isinstance(value, datetime):
            raise TypeError("pipeline evidence timestamp must be a datetime")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("pipeline evidence timestamp must be timezone-aware")
        return value.isoformat()

    def _settle_active_trade_if_due(self, timestamp: datetime) -> None:
        """Settle a legacy scheduled trade when its exit timestamp is reached."""

        trade = self.state.active_trade
        if trade is None or timestamp < trade.exit_time:
            return
        self._settle_active_trade()

    def _settle_active_trade(self) -> None:
        """Realize a legacy scheduled trade."""

        trade = self.state.active_trade
        if trade is None:
            return
        self.state.active_trade = None
        self._settle_trade(trade)

    def _settle_trade(self, trade: BacktestTrade) -> None:
        """Realize one completed trade into equity, risk, and research state."""

        updated_equity = self.state.current_equity + trade.net_profit

        self.pipeline.register_position_closed()
        self.pipeline.register_completed_trade(
            trade.net_profit,
            timestamp=trade.exit_time,
            balance_after=updated_equity,
        )

        self.state.current_equity = updated_equity
        self.state.peak_equity = max(
            self.state.peak_equity,
            self.state.current_equity,
        )
        self.state.max_drawdown = max(
            self.state.max_drawdown,
            self.state.peak_equity - self.state.current_equity,
        )
        self.state.trades.append(trade)

        if self._pending_analytics is not None:
            self.research_storage.add_trade(self._pending_analytics)

        self._pending_analytics = None
        self._position_registered = False

    def _initialize(self, historical_bars: list[MarketBar]) -> None:
        """Prepare a clean analytical, risk, research, and equity session."""

        self.reset()
        self.state.initialized = True
        self.state.running = True
        self.state.start_time = datetime.now(UTC)
        self.state.current_equity = self.config.initial_balance
        self.state.peak_equity = self.config.initial_balance

        if historical_bars:
            self.pipeline.synchronize_account_balance(
                self.config.initial_balance,
                timestamp=historical_bars[0].timestamp,
            )

    def _create_pipeline(self) -> TradingPipeline:
        return TradingPipeline(self._build_pipeline_config())

    def _build_pipeline_config(self):
        """Apply explicit BacktestConfig precedence to the active pipeline."""

        maximum_open_positions = self.config.max_open_positions
        if (
            isinstance(maximum_open_positions, bool)
            or not isinstance(maximum_open_positions, int)
        ):
            raise TypeError("max_open_positions must be an integer")
        if maximum_open_positions != 1:
            raise ValueError(
                "BacktestingEngine currently supports exactly one active "
                "position; max_open_positions must be 1"
            )

        profile = self.execution_profile
        instrument = profile.instrument if profile is not None else None
        costs = profile.costs if profile is not None else None
        risk_config = replace(
            self.config.pipeline.risk_manager,
            lot_sizing_mode=RiskLotSizingMode(self.config.lot_mode.value),
            fixed_lot_size=self.config.fixed_lot_size,
            risk_percent=self.config.risk_percent,
            use_virtual_balance=self.config.use_virtual_balance,
            virtual_balance=self.config.virtual_balance,
            minimum_position_size=(
                instrument.minimum_volume
                if instrument is not None
                else self.config.minimum_lot
            ),
            maximum_position_size=(
                instrument.maximum_volume
                if instrument is not None
                else self.config.maximum_lot
            ),
            maximum_open_positions=maximum_open_positions,
            allow_multiple_positions=False,
            spread_points=(
                costs.spread_points
                if costs is not None
                else self.config.spread_points
            ),
            commission_per_lot=(
                costs.commission_per_lot
                if costs is not None
                else self.config.commission_per_lot
            ),
            slippage_points=(
                costs.slippage_points
                if costs is not None
                else self.config.slippage_points
            ),
        )
        return replace(self.config.pipeline, risk_manager=risk_config)

    def _prepare_historical_bars(
        self,
        context: MarketContext,
    ) -> list[MarketBar]:
        if context is None:
            raise ValueError("context cannot be None")

        bars = list(context.m5_bars)
        previous_timestamp: datetime | None = None

        for bar in bars:
            timestamp = bar.timestamp
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("historical bar timestamps must be timezone-aware")
            if previous_timestamp is not None and timestamp <= previous_timestamp:
                raise ValueError(
                    "historical M5 bars must be strictly increasing without "
                    "duplicate timestamps"
                )
            previous_timestamp = timestamp

        start_date = self._validate_optional_boundary(
            self.config.start_date,
            "start_date",
        )
        end_date = self._validate_optional_boundary(
            self.config.end_date,
            "end_date",
        )
        if start_date is not None and end_date is not None and start_date > end_date:
            raise ValueError("start_date must not be after end_date")

        return [
            bar
            for bar in bars
            if (start_date is None or bar.timestamp >= start_date)
            and (end_date is None or bar.timestamp <= end_date)
        ]

    def _prepare_simulation_bars(
        self,
        context: MarketContext,
    ) -> list[MarketBar]:
        """Return strictly ordered M15 bars retained for simulator economics."""

        bars = list(context.m15_bars)
        previous_timestamp: datetime | None = None
        for bar in bars:
            timestamp = bar.timestamp
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("simulation bar timestamps must be timezone-aware")
            if previous_timestamp is not None and timestamp <= previous_timestamp:
                raise ValueError(
                    "historical M15 bars must be strictly increasing without "
                    "duplicate timestamps"
                )
            previous_timestamp = timestamp

        start_date = self._validate_optional_boundary(
            self.config.start_date,
            "start_date",
        )
        end_date = self._validate_optional_boundary(
            self.config.end_date,
            "end_date",
        )
        return [
            bar
            for bar in bars
            if (start_date is None or bar.timestamp >= start_date)
            and (end_date is None or bar.timestamp <= end_date)
        ]

    def _direction_is_enabled(self, result: PipelineResult) -> bool:
        trade_plan = result.trade_plan
        signal = trade_plan.signal if trade_plan is not None else None
        direction = signal.direction if signal is not None else SignalDirection.HOLD

        if direction == SignalDirection.BUY:
            return self.config.allow_long_positions
        if direction == SignalDirection.SELL:
            return self.config.allow_short_positions
        return False

    def _maximum_trades_reached(self) -> bool:
        maximum = self.config.maximum_trades
        if maximum is None:
            return False
        if isinstance(maximum, bool) or not isinstance(maximum, int):
            raise TypeError("maximum_trades must be an integer or None")
        if maximum < 0:
            raise ValueError("maximum_trades cannot be negative")
        return self.state.executed_trade_count >= maximum

    def _print_debug_result(self, *, index: int, result: PipelineResult) -> None:
        signal = result.signal
        trade_plan = result.trade_plan
        print("=" * 60)
        print(f"Bar #{index}")
        print(
            "Signal:",
            signal.signal if signal is not None else None,
            "| Confidence:",
            round(signal.confidence, 3) if signal is not None else 0.0,
        )
        print("Risk:", trade_plan.decision if trade_plan is not None else None)
        print("Reason:", trade_plan.reason if trade_plan is not None else "")

    def _report_progress(
        self,
        *,
        index: int,
        total_bars: int,
        force: bool = False,
    ) -> None:
        interval = self.progress_interval_bars
        if interval is None or total_bars < interval:
            return
        processed = index + 1
        if not force and processed % interval != 0 and processed != total_bars:
            return
        active = "yes" if self._has_active_position() else "no"
        elapsed = 0.0
        if self._progress_started_at is not None:
            elapsed = max(0.0, perf_counter() - self._progress_started_at)
        rate = processed / elapsed if elapsed > 0.0 else 0.0
        remaining = max(0, total_bars - processed)
        eta_seconds = remaining / rate if rate > 0.0 else 0.0
        print(
            "[Backtest] "
            f"processed {processed:,}/{total_bars:,} bars | "
            f"rate {rate:,.2f} bars/s | "
            f"elapsed {self._format_duration(elapsed)} | "
            f"ETA {self._format_duration(eta_seconds)} | "
            f"trades {len(self.state.trades):,} completed / "
            f"{self.state.executed_trade_count:,} entered | "
            f"equity {self.state.current_equity:,.2f} | "
            f"active {active}"
        )

    @staticmethod
    def _format_duration(seconds: float) -> str:
        total = max(0, round(seconds))
        hours, remainder = divmod(total, 3_600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    @staticmethod
    def _validate_mtf_window(value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("multi_timeframe_window_bars must be an integer")
        if value < 2:
            raise ValueError(
                "multi_timeframe_window_bars must be at least 2"
            )
        return value

    @staticmethod
    def _validate_progress_interval(value: int | None) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("progress_interval_bars must be an integer or None")
        if value <= 0:
            raise ValueError("progress_interval_bars must be greater than zero")
        return value

    @staticmethod
    def _validate_optional_boundary(
        value: datetime | None,
        name: str,
    ) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, datetime):
            raise TypeError(f"{name} must be a datetime or None")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{name} must be timezone-aware")
        return value

    @staticmethod
    def _require_positive_finite(value: float, name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a real number")
        converted = float(value)
        if not isfinite(converted) or converted <= 0.0:
            raise ValueError(f"{name} must be finite and greater than zero")
        return converted

    @staticmethod
    def _calculate_result_statistics(
        trades: Sequence[BacktestTrade],
    ) -> dict[str, float | int]:
        profits = [trade.net_profit for trade in trades]
        wins = [profit for profit in profits if profit > 0.0]
        losses = [profit for profit in profits if profit < 0.0]

        max_win_streak = 0
        max_loss_streak = 0
        current_win_streak = 0
        current_loss_streak = 0
        for trade in trades:
            outcome_name = getattr(trade.outcome, "name", str(trade.outcome))
            if outcome_name == "WIN":
                current_win_streak += 1
                current_loss_streak = 0
            elif outcome_name == "LOSS":
                current_loss_streak += 1
                current_win_streak = 0
            else:
                current_win_streak = 0
                current_loss_streak = 0
            max_win_streak = max(max_win_streak, current_win_streak)
            max_loss_streak = max(max_loss_streak, current_loss_streak)

        return {
            "expectancy": sum(profits) / len(profits) if profits else 0.0,
            "average_win": sum(wins) / len(wins) if wins else 0.0,
            "average_loss": (
                abs(sum(losses) / len(losses)) if losses else 0.0
            ),
            "largest_win": max(wins, default=0.0),
            "largest_loss": abs(min(losses, default=0.0)),
            "consecutive_wins": max_win_streak,
            "consecutive_losses": max_loss_streak,
        }

    def _finalize(self) -> BacktestResult:
        """Finish the simulation and calculate summary statistics."""

        if self._active_simulation is not None:
            simulation = self._active_simulation
            if simulation.is_pending_entry:
                # No completed bar existed after the observation bar, so no
                # market fill occurred and no position lifecycle was opened.
                self._active_simulation = None
                self._active_pipeline_result = None
                self._active_observation_bar = None
            else:
                completed = self.simulator.finalize_at_end_of_data(simulation)
                self._complete_incremental_trade(completed)

        # Defensive settlement for a custom legacy simulator.
        if self.state.active_trade is not None:
            self._settle_active_trade()

        self.state.running = False
        self.state.completed = True
        self.state.end_time = datetime.now(UTC)

        total_trades = len(self.state.trades)
        wins = sum(trade.outcome.name == "WIN" for trade in self.state.trades)
        losses = sum(trade.outcome.name == "LOSS" for trade in self.state.trades)
        breakeven = total_trades - wins - losses
        net_profit = sum(trade.net_profit for trade in self.state.trades)

        average_probability = self.research_engine.average_probability
        average_confidence = self.research_engine.average_confidence
        average_feature_count = (
            sum(
                len(trade.features.features)
                for trade in self.research_storage.get_trades()
            )
            / self.research_engine.total_trades
            if self.research_engine.total_trades > 0
            else 0.0
        )

        average_trade_quality = (
            sum(
                float(trade.metadata.get("trade_quality_score") or 0.0)
                for trade in self.state.trades
            )
            / total_trades
            if total_trades > 0
            else 0.0
        )
        average_trade_quality_confidence = (
            sum(
                float(
                    trade.metadata.get("trade_quality_confidence") or 0.0
                )
                for trade in self.state.trades
            )
            / total_trades
            if total_trades > 0
            else 0.0
        )
        excellent_quality_trades = sum(
            trade.metadata.get("trade_quality_level") == "EXCELLENT"
            for trade in self.state.trades
        )
        high_quality_trades = sum(
            trade.metadata.get("trade_quality_level") == "HIGH"
            for trade in self.state.trades
        )
        medium_quality_trades = sum(
            trade.metadata.get("trade_quality_level") == "MEDIUM"
            for trade in self.state.trades
        )
        low_quality_trades = sum(
            trade.metadata.get("trade_quality_level") == "LOW"
            for trade in self.state.trades
        )
        rejected_quality_trades = sum(
            trade.metadata.get("trade_quality_level") == "REJECTED"
            for trade in self.state.trades
        )

        gross_profit = sum(max(trade.net_profit, 0.0) for trade in self.state.trades)
        gross_loss = abs(
            sum(min(trade.net_profit, 0.0) for trade in self.state.trades)
        )
        profit_factor = gross_profit / gross_loss if gross_loss > 0.0 else 0.0
        result_statistics = self._calculate_result_statistics(
            self.state.trades
        )

        analysis = self.research_engine.win_loss_analysis

        print("\n" + "=" * 70)
        print("RESEARCH SUMMARY")
        print("=" * 70)
        print(f"Average Probability : {average_probability:.3f}")
        print(f"Average Confidence  : {average_confidence:.3f}")
        print(f"Average Features    : {average_feature_count:.2f}")
        print("=" * 70)
        print()
        print("=" * 70)
        print("WIN vs LOSS ANALYSIS")
        print("=" * 70)
        print(f"Winning Probability : {analysis.winning_probability:.3f}")
        print(f"Losing Probability  : {analysis.losing_probability:.3f}")
        print()
        print(f"Winning Structure   : {analysis.winning_structure:.3f}")
        print(f"Losing Structure    : {analysis.losing_structure:.3f}")
        print()
        print(f"Winning Liquidity   : {analysis.winning_liquidity:.3f}")
        print(f"Losing Liquidity    : {analysis.losing_liquidity:.3f}")
        print()
        print("FEATURE SEPARATION")
        print("-" * 70)
        print(f"Probability Gap : {analysis.probability_gap:+.3f}")
        print(f"Structure Gap   : {analysis.structure_gap:+.3f}")
        print(f"Liquidity Gap   : {analysis.liquidity_gap:+.3f}")
        print("=" * 70)

        report_builder = ResearchReportBuilder(self.research_engine)
        print()
        print(report_builder.build_feature_importance_report())

        return BacktestResult(
            total_trades=total_trades,
            winning_trades=wins,
            losing_trades=losses,
            breakeven_trades=breakeven,
            net_profit=net_profit,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            profit_factor=profit_factor,
            expectancy=result_statistics["expectancy"],
            average_win=result_statistics["average_win"],
            average_loss=result_statistics["average_loss"],
            largest_win=result_statistics["largest_win"],
            largest_loss=result_statistics["largest_loss"],
            consecutive_wins=result_statistics["consecutive_wins"],
            consecutive_losses=result_statistics["consecutive_losses"],
            win_rate=(wins / total_trades * 100.0 if total_trades > 0 else 0.0),
            max_drawdown=self.state.max_drawdown,
            trades=self.state.trades.copy(),
            average_probability=average_probability,
            average_confidence=average_confidence,
            average_feature_count=average_feature_count,
            average_trade_quality=average_trade_quality,
            average_trade_quality_confidence=average_trade_quality_confidence,
            excellent_quality_trades=excellent_quality_trades,
            high_quality_trades=high_quality_trades,
            medium_quality_trades=medium_quality_trades,
            low_quality_trades=low_quality_trades,
            rejected_quality_trades=rejected_quality_trades,
        )
