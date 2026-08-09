"""
Historical Backtest Runner.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import MetaTrader5 as mt5

from core.execution_economics.models import ExecutionEconomicsProfile

from .candidate_outcome_exporter import CandidateOutcomeExporter
from .candidate_outcome_segmentation import (
    CandidateOutcomeSegmentationCalculator,
)
from .config import BacktestConfig
from .engine import BacktestingEngine
from .exporter import BacktestExporter
from .methodology_candidate_rule_simulator import (
    MethodologyCandidateRuleSimulator,
)
from .methodology_condition_analytics import MethodologyConditionAnalytics
from .methodology_condition_outcome_attribution import (
    MethodologyConditionOutcomeAttribution,
)
from .methodology_counterfactual_cohorts import (
    MethodologyCounterfactualCohorts,
)
from .methodology_diagnostics_exporter import (
    MethodologyDiagnosticsExporter,
)
from .methodology_outcome_integrity import (
    MethodologyOutcomeIntegrityAnalytics,
)
from .methodology_outcome_research import MethodologyOutcomeResearch
from .methodology_outcome_stability import (
    MethodologyOutcomeStabilityAnalytics,
)
from .methodology_shadow_decision_comparison import (
    MethodologyShadowDecisionComparison,
)
from .methodology_variant_b_alignment_integrity import (
    MethodologyVariantBAlignmentIntegrity,
)
from .methodology_variant_b_atr_shadow_matrix import (
    MethodologyVariantBATRShadowMatrix,
)
from .methodology_variant_b_cluster_selection import (
    MethodologyVariantBClusterSelection,
)
from .methodology_variant_b_confirmation_delay import (
    MethodologyVariantBConfirmationDelay,
)
from .methodology_variant_b_cost_sensitivity import (
    MethodologyVariantBCostSensitivity,
)
from .methodology_variant_b_execution_context import (
    MethodologyVariantBExecutionContext,
)
from .methodology_variant_b_execution_diagnostics import (
    MethodologyVariantBExecutionDiagnostics,
)
from .methodology_variant_b_probability_subset import (
    MethodologyVariantBProbabilitySubset,
)
from .methodology_variant_b_shadow_exception_monitor import (
    MethodologyVariantBShadowExceptionMonitor,
)
from .methodology_variant_b_shadow_exception_stability import (
    MethodologyVariantBShadowExceptionStability,
)
from .methodology_variant_b_shadow_integration import (
    MethodologyVariantBShadowIntegration,
)
from .methodology_variant_b_shadow_scoring import (
    MethodologyVariantBShadowScoring,
)
from .methodology_variant_b_shadow_trades import (
    MethodologyVariantBShadowTrades,
)
from .methodology_variant_b_statistical_stability import (
    MethodologyVariantBStatisticalStability,
)
from .models import BacktestReplayContext, BacktestResult
from .multi_timeframe_loader import MultiTimeframeLoader
from .reporter import (
    print_report,
    save_report,
)
from .run_output import BacktestRunOutput
from .state import BacktestState
from .statistics import StatisticsCalculator


class BacktestRunner:
    """
    Runs complete historical backtests.
    """

    def __init__(
        self,
        config: BacktestConfig,
    ) -> None:

        self.config = config
        self.execution_profile = config.resolved_execution_profile()
        instrument = self.execution_profile.instrument

        self.state = BacktestState()

        self.loader = MultiTimeframeLoader()

        self.engine = BacktestingEngine(
            config,
            stop_loss_distance=instrument.minimum_stop_distance,
            tick_size=instrument.tick_size,
            tick_value_per_lot=instrument.tick_value_per_lot,
            lot_step=instrument.volume_step,
            execution_profile=self.execution_profile,
        )

        self.exporter = BacktestExporter(
            config.output_directory,
        )

        self.methodology_exporter = MethodologyDiagnosticsExporter(
            config.output_directory,
        )

        self.methodology_condition_analytics = MethodologyConditionAnalytics(
            config.output_directory,
        )

        self.methodology_condition_outcome_attribution = (
            MethodologyConditionOutcomeAttribution(
                config.output_directory,
            )
        )

        self.methodology_counterfactual_cohorts = (
            MethodologyCounterfactualCohorts(
                config.output_directory,
            )
        )

        self.methodology_candidate_rule_simulator = (
            MethodologyCandidateRuleSimulator(
                config.output_directory,
            )
        )

        self.methodology_shadow_decision_comparison = (
            MethodologyShadowDecisionComparison(
                config.output_directory,
            )
        )

        self.methodology_variant_b_shadow_scoring = (
            MethodologyVariantBShadowScoring(
                config.output_directory,
            )
        )

        self.methodology_variant_b_shadow_trades = (
            MethodologyVariantBShadowTrades(
                config,
                config.output_directory,
                tick_size=self.engine.tick_size,
                tick_value_per_lot=self.engine.tick_value_per_lot,
            )
        )

        self.methodology_variant_b_execution_diagnostics = (
            MethodologyVariantBExecutionDiagnostics(
                config.output_directory,
            )
        )

        self.methodology_variant_b_atr_shadow_matrix = (
            MethodologyVariantBATRShadowMatrix(
                config.output_directory,
            )
        )

        self.methodology_variant_b_cost_sensitivity = (
            MethodologyVariantBCostSensitivity(
                config.output_directory,
            )
        )

        self.methodology_variant_b_execution_context = (
            MethodologyVariantBExecutionContext(
                config.output_directory,
            )
        )

        self.methodology_variant_b_cluster_selection = (
            MethodologyVariantBClusterSelection(
                config.output_directory,
            )
        )

        self.methodology_variant_b_confirmation_delay = (
            MethodologyVariantBConfirmationDelay(
                config.output_directory,
            )
        )

        self.methodology_variant_b_statistical_stability = (
            MethodologyVariantBStatisticalStability(
                config.output_directory,
            )
        )

        self.methodology_variant_b_shadow_integration = (
            MethodologyVariantBShadowIntegration(
                config.output_directory,
            )
        )

        self.methodology_variant_b_alignment_integrity = (
            MethodologyVariantBAlignmentIntegrity(
                config.output_directory,
            )
        )

        self.methodology_variant_b_probability_subset = (
            MethodologyVariantBProbabilitySubset(
                config.output_directory,
            )
        )

        self.methodology_variant_b_shadow_exception_monitor = (
            MethodologyVariantBShadowExceptionMonitor(
                config.output_directory,
            )
        )

        self.methodology_variant_b_shadow_exception_stability = (
            MethodologyVariantBShadowExceptionStability(
                config.output_directory,
            )
        )

        self.methodology_outcome_research = MethodologyOutcomeResearch(
            config.output_directory,
        )

        self.methodology_outcome_integrity = (
            MethodologyOutcomeIntegrityAnalytics(
                config.output_directory,
            )
        )

        self.methodology_outcome_stability = (
            MethodologyOutcomeStabilityAnalytics(
                config.output_directory,
            )
        )

        self._last_m5_bars: tuple[object, ...] = ()
        self._last_requested_end_time: datetime | None = None
        self._last_actual_window: dict[str, object] = {}

        self.candidate_outcome_exporter = CandidateOutcomeExporter(
            config.output_directory,
        )

        self.statistics = StatisticsCalculator()

    def run(
        self,
        symbol: str,
        timeframe: int,
        bars: int,
        *,
        end_time: datetime | None = None,
    ) -> BacktestResult:
        """
        Execute a complete historical backtest.
        """

        self._validate_timeframe(timeframe)
        self._validate_profile_symbol(symbol)
        self.state.reset()

        context = self._load_context(
            symbol=symbol,
            bars=bars,
            end_time=end_time,
        )

        if not context.m5_bars:
            raise RuntimeError(
                "No historical data returned."
            )

        result = self.engine.run(context)
        self._capture_historical_window(
            context=context,
            requested_end_time=end_time,
            requested_bars=bars,
        )

        self._complete_state(
            processed_bar_count=self._eligible_m5_count(context),
            executed_trade_count=result.total_trades,
        )

        return result

    def run_with_strategy_comparison(
        self,
        symbol: str,
        timeframe: int,
        bars: int,
        *,
        end_time: datetime | None = None,
    ) -> BacktestRunOutput:
        """Execute one backtest and return result plus strategy comparison.

        This additive entry point preserves :meth:`run` and its existing
        ``BacktestResult`` return contract.
        """

        self._validate_timeframe(timeframe)
        self._validate_profile_symbol(symbol)
        self.state.reset()

        context = self._load_context(
            symbol=symbol,
            bars=bars,
            end_time=end_time,
        )

        if not context.m5_bars:
            raise RuntimeError(
                "No historical data returned."
            )

        output = self.engine.run_with_strategy_comparison(context)
        self._capture_historical_window(
            context=context,
            requested_end_time=end_time,
            requested_bars=bars,
        )

        self._complete_state(
            processed_bar_count=self._eligible_m5_count(context),
            executed_trade_count=output.result.total_trades,
        )

        return output

    def _load_context(
        self,
        *,
        symbol: str,
        bars: int,
        end_time: datetime | None,
    ) -> object:
        """Load one M5-eligible replay with shared warm-up requirements."""

        return self.loader.load(
            symbol=symbol,
            bars=bars,
            end_time=end_time,
            warmup_bars=self.config.warmup_bars,
            analysis_window_bars=getattr(
                self.engine,
                "multi_timeframe_window_bars",
                500,
            ),
        )

    def _capture_historical_window(
        self,
        *,
        context: object,
        requested_end_time: datetime | None,
        requested_bars: int,
    ) -> None:
        """Retain deterministic window provenance for research reports."""

        m5_bars = tuple(getattr(context, "m5_bars", ()))
        m15_bars = tuple(getattr(context, "m15_bars", ()))
        h1_bars = tuple(getattr(context, "h1_bars", ()))
        h4_bars = tuple(getattr(context, "h4_bars", ()))
        self._last_m5_bars = m5_bars
        self._last_requested_end_time = (
            requested_end_time.astimezone(UTC)
            if requested_end_time is not None
            else None
        )

        def normalized_timestamp(value: object) -> str | None:
            timestamp = getattr(value, "timestamp", None)
            if not isinstance(timestamp, datetime):
                return None
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                return None
            return timestamp.astimezone(UTC).isoformat()

        def first_timestamp(values: tuple[object, ...]) -> str | None:
            if not values:
                return None
            return normalized_timestamp(values[0])

        def last_timestamp(values: tuple[object, ...]) -> str | None:
            if not values:
                return None
            return normalized_timestamp(values[-1])

        config = getattr(self, "config", None)
        if config is None:
            # Compatibility for focused tests and legacy integrations that
            # intentionally construct BacktestRunner without calling __init__.
            config = BacktestConfig()
        execution_profile = getattr(self, "execution_profile", None)
        if not isinstance(execution_profile, ExecutionEconomicsProfile):
            execution_profile = config.resolved_execution_profile()
        instrument = execution_profile.instrument
        costs = execution_profile.costs

        replay_window = (
            context.replay_window
            if isinstance(context, BacktestReplayContext)
            else None
        )
        self._last_actual_window = {
            "requested_eligible_m5_bars": requested_bars,
            "requested_end_time": (
                self._last_requested_end_time.isoformat()
                if self._last_requested_end_time is not None
                else None
            ),
            "source_start_time": (
                replay_window.source_start.isoformat()
                if replay_window is not None
                else first_timestamp(m5_bars)
            ),
            "source_end_time": (
                replay_window.source_end.isoformat()
                if replay_window is not None
                else self._last_requested_end_time.isoformat()
                if self._last_requested_end_time is not None
                else None
            ),
            "first_eligible_m5_timestamp": (
                replay_window.first_eligible_m5_timestamp.isoformat()
                if replay_window is not None
                else first_timestamp(m5_bars)
            ),
            "last_eligible_m5_timestamp": (
                replay_window.last_eligible_m5_timestamp.isoformat()
                if replay_window is not None
                else last_timestamp(m5_bars)
            ),
            "analysis_window_bars": (
                replay_window.analysis_window_bars
                if replay_window is not None
                else getattr(self.engine, "multi_timeframe_window_bars", None)
            ),
            "required_warmup_snapshots": (
                replay_window.required_warmup_snapshots
                if replay_window is not None
                else config.warmup_bars
            ),
            "available_warmup_snapshots": (
                replay_window.available_warmup_snapshots
                if replay_window is not None
                else None
            ),
            "requested_bar_counts": (
                dict(replay_window.requested_bar_counts)
                if replay_window is not None
                else None
            ),
            "actual": {
                "m5": {
                    "count": len(m5_bars),
                    "first_timestamp": first_timestamp(m5_bars),
                    "last_timestamp": last_timestamp(m5_bars),
                },
                "m15": {
                    "count": len(m15_bars),
                    "first_timestamp": first_timestamp(m15_bars),
                    "last_timestamp": last_timestamp(m15_bars),
                },
                "h1": {
                    "count": len(h1_bars),
                    "first_timestamp": first_timestamp(h1_bars),
                    "last_timestamp": last_timestamp(h1_bars),
                },
                "h4": {
                    "count": len(h4_bars),
                    "first_timestamp": first_timestamp(h4_bars),
                    "last_timestamp": last_timestamp(h4_bars),
                },
            },
            "execution_cost_assumptions": {
                "profile": costs.profile_id,
                "verified": costs.verified,
                "spread_points": costs.spread_points,
                "slippage_points": costs.slippage_points,
                "commission_per_trade": costs.commission_per_trade,
                "commission_per_lot": costs.commission_per_lot,
                "spread_source": costs.spread_source,
                "historical_spread_field_used": (
                    costs.historical_spread_field_used
                ),
                "spread_definition": (
                    "Pinned round-trip spread assumption applied by the "
                    "historical simulator; historical bar spread is unused."
                ),
                "slippage_definition": (
                    "Configured adverse points used by the simulator; this "
                    "is separate from MT5 order-deviation tolerance."
                ),
                "commission_definition": (
                    "Explicit account-specific assumptions; not inferred "
                    "from MT5 symbol metadata."
                ),
            },
            "execution_economics": execution_profile.to_dict(),
            "instrument_specification_provenance": {
                "specification_id": instrument.specification_id,
                "provenance": instrument.provenance.value,
                "source": instrument.source,
                "captured_at": (
                    instrument.captured_at.astimezone(UTC).isoformat()
                    if instrument.captured_at is not None
                    else None
                ),
                "historical_specification_verified": (
                    instrument.historical_specification_verified
                ),
                "contract_size": instrument.contract_size,
            },
            "research_account_economics": {
                "risk_capital_source": (
                    execution_profile.research_risk_capital_source.value
                ),
                "initial_balance": config.initial_balance,
                "mark_to_market_equity_modeled": False,
            },
            "closed_candle_only": True,
            "no_lookahead": True,
            "decision_clock": "M5",
            "simulation_clock": "M15_COMPLETED",
        }

    @staticmethod
    def _validate_timeframe(timeframe: int) -> None:
        if isinstance(timeframe, bool) or not isinstance(timeframe, int):
            raise TypeError("timeframe must be an integer MT5 constant")
        if timeframe != mt5.TIMEFRAME_M5:
            raise ValueError("BacktestRunner timeframe must be TIMEFRAME_M5")

    def _validate_profile_symbol(self, symbol: str) -> None:
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol must be a non-empty string")
        execution_profile = getattr(self, "execution_profile", None)
        if not isinstance(execution_profile, ExecutionEconomicsProfile):
            config = getattr(self, "config", None)
            if not isinstance(config, BacktestConfig):
                return
            execution_profile = config.resolved_execution_profile()
        configured = execution_profile.instrument.symbol
        if symbol != configured:
            raise ValueError(
                "backtest symbol must match the pinned execution profile: "
                f"expected={configured} received={symbol}"
            )

    @staticmethod
    def _eligible_m5_count(context: object) -> int:
        if isinstance(context, BacktestReplayContext):
            return context.replay_window.requested_eligible_m5_bars
        return len(tuple(getattr(context, "m5_bars", ())))

    def _complete_state(
        self,
        *,
        processed_bar_count: int,
        executed_trade_count: int,
    ) -> None:
        """Publish one completed runner state consistently."""

        self.state.processed_bar_count = processed_bar_count
        self.state.executed_trade_count = executed_trade_count
        self.state.completed = True

    def generate_reports(
        self,
        result: BacktestResult,
    ) -> None:
        """
        Generate all Sprint 1 reports plus observational methodology artifacts.
        """

        output_dir = Path(
            self.config.output_directory,
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        print_report(result)

        save_report(
            result,
            output_dir / "backtest_report.txt",
        )

        self.exporter.export_summary(result)

        self.exporter.export_trade_log(result)

        self.exporter.export_observation_audit(
            self.engine.observation_audits,
        )

        self.exporter.export_rejection_summary(
            self.engine.observation_audits,
        )

        self.exporter.export_equity_curve(
            result,
            self.config.initial_balance,
        )

        stats = self.statistics.calculate(result)

        self.exporter.export_statistics(
            asdict(stats),
        )

        (output_dir / "historical_window.json").write_text(
            json.dumps(
                self._last_actual_window,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        methodology_observations = tuple(
            getattr(self.engine, "methodology_observations", ())
        )
        methodology_summary_method = getattr(
            self.engine,
            "methodology_summary",
            None,
        )
        methodology_summary = (
            methodology_summary_method()
            if callable(methodology_summary_method)
            else {}
        )
        self.methodology_exporter.export_observations(
            methodology_observations,
        )
        self.methodology_exporter.export_summary(
            methodology_summary,
            total_observations=len(methodology_observations),
        )
        self.methodology_condition_analytics.export(
            methodology_observations,
        )
        methodology_outcomes = self.methodology_outcome_research.evaluate(
            methodology_observations,
            self._last_m5_bars,
        )
        self.methodology_outcome_research.export(methodology_outcomes)
        self.methodology_outcome_integrity.export(
            methodology_observations,
            self._last_m5_bars,
            methodology_outcomes,
            horizons=self.methodology_outcome_research.horizons,
        )
        self.methodology_outcome_stability.export(
            methodology_outcomes,
        )
        self.methodology_condition_outcome_attribution.export(
            methodology_observations,
            methodology_outcomes,
            window_metadata=self._last_actual_window,
        )
        self.methodology_counterfactual_cohorts.export(
            methodology_observations,
            methodology_outcomes,
            window_metadata=self._last_actual_window,
        )
        self.methodology_candidate_rule_simulator.export(
            methodology_observations,
            methodology_outcomes,
            window_metadata=self._last_actual_window,
        )
        self.methodology_shadow_decision_comparison.export(
            methodology_observations,
            tuple(self.engine.observation_audits),
            methodology_outcomes,
            window_metadata=self._last_actual_window,
        )
        self.methodology_variant_b_shadow_scoring.export(
            methodology_observations,
            tuple(self.engine.observation_audits),
            methodology_outcomes,
            window_metadata=self._last_actual_window,
        )
        self.methodology_variant_b_shadow_trades.export(
            methodology_observations,
            self._last_m5_bars,
            window_metadata=self._last_actual_window,
        )
        self.methodology_variant_b_execution_diagnostics.export(
            methodology_observations,
            self._last_m5_bars,
            window_metadata=self._last_actual_window,
        )
        self.methodology_variant_b_atr_shadow_matrix.export(
            methodology_observations,
            self._last_m5_bars,
            window_metadata=self._last_actual_window,
        )
        self.methodology_variant_b_cost_sensitivity.export(
            methodology_observations,
            self._last_m5_bars,
            window_metadata=self._last_actual_window,
        )
        self.methodology_variant_b_execution_context.export(
            methodology_observations,
            self._last_m5_bars,
            window_metadata=self._last_actual_window,
        )
        self.methodology_variant_b_cluster_selection.export(
            methodology_observations,
            self._last_m5_bars,
            window_metadata=self._last_actual_window,
        )
        self.methodology_variant_b_confirmation_delay.export(
            methodology_observations,
            self._last_m5_bars,
            window_metadata=self._last_actual_window,
        )
        self.methodology_variant_b_statistical_stability.export(
            methodology_observations,
            self._last_m5_bars,
            window_metadata=self._last_actual_window,
        )
        self.methodology_variant_b_shadow_integration.export(
            methodology_observations,
            tuple(self.engine.observation_audits),
            self._last_m5_bars,
            window_metadata=self._last_actual_window,
        )
        self.methodology_variant_b_alignment_integrity.export(
            methodology_observations,
            tuple(self.engine.observation_audits),
            self._last_m5_bars,
            window_metadata=self._last_actual_window,
        )
        self.methodology_variant_b_probability_subset.export(
            methodology_observations,
            tuple(self.engine.observation_audits),
            self._last_m5_bars,
            window_metadata=self._last_actual_window,
        )
        self.methodology_variant_b_shadow_exception_monitor.export(
            methodology_observations,
            tuple(self.engine.observation_audits),
            self._last_m5_bars,
            window_metadata=self._last_actual_window,
        )
        self.methodology_variant_b_shadow_exception_stability.export(
            methodology_observations,
            tuple(self.engine.observation_audits),
            self._last_m5_bars,
            window_metadata=self._last_actual_window,
        )

    def generate_composite_reports(
        self,
        output: BacktestRunOutput,
    ) -> None:
        """Generate execution, comparison, and candidate research artifacts."""

        if not isinstance(output, BacktestRunOutput):
            raise TypeError("output must be BacktestRunOutput")

        self.generate_reports(output.result)
        self.exporter.export_strategy_comparison_summary(
            output.strategy_comparison
        )
        self.exporter.export_strategy_comparison_events(
            output.strategy_comparison
        )
        self.exporter.export_strategy_setup_lifecycles(
            output.strategy_comparison
        )
        export_post_expiry = getattr(
            self.exporter,
            "export_strategy_post_expiry_triggers",
            None,
        )
        if callable(export_post_expiry):
            export_post_expiry(output.strategy_comparison)
        has_candidate_outcome_research = bool(
            output.candidate_outcome_evaluations
            or output.candidate_outcome_summary
        )
        if has_candidate_outcome_research:
            self.candidate_outcome_exporter.export_summary(
                output.candidate_outcome_summary
            )
            self.candidate_outcome_exporter.export_evaluations(
                output.candidate_outcome_evaluations
            )
            self.candidate_outcome_exporter.export_statistics(
                output.candidate_outcome_statistics
            )

            export_segments = getattr(
                self.candidate_outcome_exporter,
                "export_segments",
                None,
            )
            if callable(export_segments):
                segmentation = (
                    CandidateOutcomeSegmentationCalculator.calculate(
                        output.candidate_outcome_evaluations
                    )
                )
                export_segments(segmentation)

    def print_trade_log(
        self,
        result: BacktestResult,
    ) -> None:

        print()
        print("=" * 70)
        print("TRADE LOG")
        print("=" * 70)

        for index, trade in enumerate(
            result.trades,
            start=1,
        ):

            print(
                f"{index:03d} | "
                f"{trade.direction:<4} | "
                f"{trade.entry_price:.2f} -> "
                f"{trade.exit_price:.2f} | "
                f"{trade.net_profit:.2f} | "
                f"{trade.outcome.name}"
            )
