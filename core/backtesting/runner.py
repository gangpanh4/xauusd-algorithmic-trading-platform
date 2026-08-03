"""
Historical Backtest Runner.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path

from .candidate_outcome_exporter import CandidateOutcomeExporter
from .candidate_outcome_segmentation import (
    CandidateOutcomeSegmentationCalculator,
)
from .config import BacktestConfig
from .engine import BacktestingEngine
from .exporter import BacktestExporter
from .methodology_condition_analytics import MethodologyConditionAnalytics
from .methodology_condition_outcome_attribution import (
    MethodologyConditionOutcomeAttribution,
)
from .methodology_counterfactual_cohorts import (
    MethodologyCounterfactualCohorts,
)
from .methodology_candidate_rule_simulator import (
    MethodologyCandidateRuleSimulator,
)
from .methodology_shadow_decision_comparison import (
    MethodologyShadowDecisionComparison,
)
from .methodology_variant_b_shadow_scoring import (
    MethodologyVariantBShadowScoring,
)
from .methodology_variant_b_shadow_trades import (
    MethodologyVariantBShadowTrades,
)
from .methodology_variant_b_execution_diagnostics import (
    MethodologyVariantBExecutionDiagnostics,
)
from .methodology_variant_b_atr_shadow_matrix import (
    MethodologyVariantBATRShadowMatrix,
)
from .methodology_variant_b_cost_sensitivity import (
    MethodologyVariantBCostSensitivity,
)
from .methodology_variant_b_execution_context import (
    MethodologyVariantBExecutionContext,
)
from .methodology_variant_b_cluster_selection import (
    MethodologyVariantBClusterSelection,
)
from .methodology_variant_b_confirmation_delay import (
    MethodologyVariantBConfirmationDelay,
)
from .methodology_variant_b_statistical_stability import (
    MethodologyVariantBStatisticalStability,
)
from .methodology_variant_b_shadow_integration import (
    MethodologyVariantBShadowIntegration,
)
from .methodology_variant_b_alignment_integrity import (
    MethodologyVariantBAlignmentIntegrity,
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
from .models import BacktestResult
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

        self.state = BacktestState()

        self.loader = MultiTimeframeLoader()

        self.engine = BacktestingEngine(
            config,
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

        self.state.reset()

        context = self._load_context(
            symbol=symbol,
            bars=bars,
            end_time=end_time,
        )

        if not context.m15_bars:
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
            processed_bar_count=len(context.m15_bars),
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

        self.state.reset()

        context = self._load_context(
            symbol=symbol,
            bars=bars,
            end_time=end_time,
        )

        if not context.m15_bars:
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
            processed_bar_count=len(context.m15_bars),
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
        """Preserve legacy loader calls when no explicit boundary is requested."""

        if end_time is None:
            return self.loader.load(
                symbol=symbol,
                bars=bars,
            )
        return self.loader.load(
            symbol=symbol,
            bars=bars,
            end_time=end_time,
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

        self._last_actual_window = {
            "requested_bars_per_timeframe": requested_bars,
            "requested_end_time": (
                self._last_requested_end_time.isoformat()
                if self._last_requested_end_time is not None
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
            "closed_candle_only": True,
            "no_lookahead": True,
        }

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
