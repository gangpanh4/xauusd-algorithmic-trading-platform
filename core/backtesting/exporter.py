"""
Backtest export utilities.
"""

from __future__ import annotations

import csv
import json
import math
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Final

from core.trading_pipeline.models import (
    PipelineDisposition,
    PipelineObservationAudit,
)

from .models import BacktestResult, BacktestTrade
from .strategy_comparison import BacktestStrategyComparison


class BacktestExporter:
    """
    Export backtesting results to deterministic research artifacts.

    The trade log contains a stable set of analytical columns and appends any
    additional trade metadata as sorted ``Metadata:<key>`` columns. This keeps
    the export backward compatible while preventing newly introduced evidence
    from being silently discarded.
    """

    _METADATA_COLUMNS: Final[tuple[tuple[str, str], ...]] = (
        ("Signal Observation Time", "signal_observation_time"),
        ("Observation Timestamp", "observation_timestamp"),
        ("Scheduled Exit Timestamp", "scheduled_exit_timestamp"),
        ("Planned Entry Price", "planned_entry_price"),
        ("Reference Entry Price", "reference_entry_price"),
        ("Actual Entry Price", "actual_entry_price"),
        ("Effective Stop Loss", "effective_stop_loss"),
        ("Effective Take Profit", "effective_take_profit"),
        ("Probability", "probability"),
        ("Probability Confidence", "confidence"),
        ("Probability Accepted", "probability_accepted"),
        ("Probability Reasons", "probability_reasons"),
        ("Feature Count", "feature_count"),
        ("Evidence Count", "evidence_count"),
        ("Structure Confidence", "structure_confidence"),
        ("Trade Quality Score", "trade_quality_score"),
        ("Trade Quality Confidence", "trade_quality_confidence"),
        ("Trade Quality Level", "trade_quality_level"),
        ("Trade Quality Approved", "trade_quality_approved"),
        ("Trade Quality Reasons", "trade_quality_reasons"),
        ("Regime", "regime"),
        ("Regime Confidence", "regime_confidence"),
        ("Confluence Score", "confluence_score"),
        ("Confluence Approved", "confluence_approved"),
        ("Decision", "decision"),
        ("Decision Approved", "decision_approved"),
        ("Signal Score", "signal_score"),
        ("Signal Confidence", "signal_confidence"),
        ("Strategy ID", "strategy_id"),
        ("BOS Present", "bos_present"),
        ("BOS Direction", "bos_direction"),
        ("BOS Timestamp", "bos_timestamp"),
        ("BOS Break Distance", "bos_break_distance"),
        ("BOS Break ATR Multiple", "bos_break_atr_multiple"),
        ("BOS Freshness", "bos_freshness"),
        ("BOS Quality", "bos_quality"),
        ("BOS Strength", "bos_strength"),
        ("BOS Power Score", "bos_power_score"),
        ("BOS Structure Score", "bos_structure_score"),
        ("BOS Age", "bos_age"),
        ("CHOCH Present", "choch_present"),
        ("CHOCH Direction", "choch_direction"),
        ("CHOCH Timestamp", "choch_timestamp"),
        ("CHOCH Break Distance", "choch_break_distance"),
        ("CHOCH Break ATR Multiple", "choch_break_atr_multiple"),
        ("CHOCH Freshness", "choch_freshness"),
        ("CHOCH Quality", "choch_quality"),
        ("CHOCH Strength", "choch_strength"),
        ("CHOCH Power Score", "choch_power_score"),
        ("CHOCH Structure Score", "choch_structure_score"),
        ("CHOCH Age", "choch_age"),
        ("Liquidity Present", "liquidity_present"),
        ("Liquidity Timestamp", "liquidity_timestamp"),
        ("Liquidity Side", "liquidity_side"),
        ("Liquidity Sweep Distance", "liquidity_sweep_distance"),
        ("Liquidity ATR Multiple", "liquidity_atr_multiple"),
        ("Liquidity Sweep Strength", "liquidity_sweep_strength"),
        ("Liquidity Reaction Strength", "liquidity_reaction_strength"),
        ("Liquidity Reclaim Strength", "liquidity_reclaim_strength"),
        ("Liquidity Quality", "liquidity_quality"),
        ("Liquidity Age", "liquidity_age"),
        ("Liquidity Freshness", "liquidity_freshness"),
        ("Tick Size", "tick_size"),
        ("Tick Value Per Lot", "tick_value_per_lot"),
        ("Lot Step", "lot_step"),
        ("Spread Points", "spread_points"),
        ("Slippage Points", "slippage_points"),
        ("Slippage Cost", "slippage_cost"),
        ("Commission Per Trade", "commission_per_trade"),
        ("Commission Per Lot", "commission_per_lot"),
        ("Monetary Risk", "monetary_risk"),
        ("Gross R Multiple", "gross_r_multiple"),
        ("Net R Multiple", "net_r_multiple"),
        ("Execution Model ID", "execution_model_id"),
        ("Entry Policy", "entry_policy"),
        ("Entry Clock", "entry_clock"),
        ("Lifecycle Clock", "lifecycle_clock"),
        ("Execution Policy", "execution_policy"),
        ("Exit Levels Recentered", "exit_levels_recentered"),
        ("Legacy Unit Economics Fallback", "legacy_unit_economics_fallback"),
        ("Lot Sizing Mode", "lot_sizing_mode"),
        ("Working Balance", "working_balance"),
        ("Daily Start Balance", "daily_start_balance"),
        ("Daily Drawdown", "daily_drawdown"),
        ("Daily Drawdown Fraction", "daily_drawdown_fraction"),
        ("Open Position Count", "open_position_count"),
        ("Emergency Stop", "emergency_stop"),
        ("Daily Loss Limit Hit", "daily_loss_limit_hit"),
    )

    _OBSERVATION_AUDIT_COLUMNS: Final[tuple[str, ...]] = (
        "Observation Number",
        "Timestamp",
        "Disposition",
        "Stage Reached",
        "Rejection Stage",
        "Reason Code",
        "Reason",
        "Regime Confirmed",
        "BOS Present",
        "CHOCH Present",
        "Liquidity Present",
        "Feature Count",
        "Probability Calculated",
        "Probability Accepted",
        "Probability Value",
        "Trade Quality Calculated",
        "Trade Quality Approved",
        "Trade Quality Score",
        "Confluence Available",
        "Confluence Approved",
        "Confluence Score",
        "Signal Generated",
        "Risk Approved",
    )

    _BASE_COLUMNS: Final[tuple[str, ...]] = (
        "Trade Number",
        "Entry Time",
        "Exit Time",
        "Direction",
        "Outcome",
        "Exit Reason",
        "Entry Price",
        "Exit Price",
        "Position Size",
        "Spread Cost",
        "Commission",
        "Gross Profit",
        "Net Profit",
        "Holding Bars",
        "Holding Time",
        "Holding Seconds",
        "Risk Reward",
        "Maximum Favorable Excursion",
        "Maximum Adverse Excursion",
        "Highest Price",
        "Lowest Price",
        "Breakeven Triggered",
        "Trailing Stop Triggered",
        "Partial Exit Taken",
        "Lifecycle Events",
    )

    def __init__(
        self,
        output_directory: str | Path = "output/backtests",
    ) -> None:
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    def export_summary(
        self,
        result: BacktestResult,
        *,
        execution_model_provenance: Mapping[str, object] | None = None,
    ) -> Path:
        """Export a complete ``summary.json``."""

        summary: dict[str, object] = {
            "total_trades": result.total_trades,
            "winning_trades": result.winning_trades,
            "losing_trades": result.losing_trades,
            "breakeven_trades": result.breakeven_trades,
            "win_rate": result.win_rate,
            "net_profit": result.net_profit,
            "gross_profit": result.gross_profit,
            "gross_loss": result.gross_loss,
            "profit_factor": result.profit_factor,
            "expectancy": result.expectancy,
            "max_drawdown": result.max_drawdown,
            "average_win": result.average_win,
            "average_loss": result.average_loss,
            "largest_win": result.largest_win,
            "largest_loss": result.largest_loss,
            "consecutive_wins": result.consecutive_wins,
            "consecutive_losses": result.consecutive_losses,
            "average_probability": result.average_probability,
            "average_confidence": result.average_confidence,
            "average_feature_count": result.average_feature_count,
            "average_trade_quality": result.average_trade_quality,
            "average_trade_quality_confidence": (
                result.average_trade_quality_confidence
            ),
            "excellent_quality_trades": result.excellent_quality_trades,
            "high_quality_trades": result.high_quality_trades,
            "medium_quality_trades": result.medium_quality_trades,
            "low_quality_trades": result.low_quality_trades,
            "rejected_quality_trades": result.rejected_quality_trades,
        }
        self._attach_execution_model_provenance(
            summary,
            execution_model_provenance,
        )

        path = self.output_directory / "summary.json"
        self._write_json(path, summary)
        return path

    def export_trade_log(
        self,
        result: BacktestResult,
    ) -> Path:
        """
        Export a research-grade ``trade_log.csv``.

        Missing evidence is exported as an empty cell rather than a fabricated
        zero. This distinction is essential when diagnosing disconnected
        strategy components.
        """

        path = self.output_directory / "trade_log.csv"
        flattened_metadata = [
            self._flatten_metadata(trade.metadata)
            for trade in result.trades
        ]
        standard_keys = {key for _, key in self._METADATA_COLUMNS}
        extra_keys = sorted(
            {
                key
                for metadata in flattened_metadata
                for key in metadata
                if key not in standard_keys
            }
        )
        fieldnames = [
            *self._BASE_COLUMNS,
            *(heading for heading, _ in self._METADATA_COLUMNS),
            *(f"Metadata:{key}" for key in extra_keys),
            "Metadata JSON",
        ]

        with path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames,
                extrasaction="raise",
            )
            writer.writeheader()

            for index, (trade, metadata) in enumerate(
                zip(result.trades, flattened_metadata, strict=True),
                start=1,
            ):
                writer.writerow(
                    self._build_trade_row(
                        trade_number=index,
                        trade=trade,
                        metadata=metadata,
                        extra_keys=extra_keys,
                    )
                )

        return path

    def export_observation_audit(
        self,
        audits: Sequence[PipelineObservationAudit],
    ) -> Path:
        """Export one row per processed observation."""

        validated = self._validate_observation_audits(audits)
        path = self.output_directory / "observation_audit.csv"

        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=list(self._OBSERVATION_AUDIT_COLUMNS),
                extrasaction="raise",
            )
            writer.writeheader()
            for index, audit in enumerate(validated, start=1):
                writer.writerow(
                    {
                        "Observation Number": index,
                        "Timestamp": audit.timestamp.isoformat(),
                        "Disposition": audit.disposition.value,
                        "Stage Reached": audit.stage_reached.value,
                        "Rejection Stage": (
                            audit.rejection_stage.value
                            if audit.rejection_stage is not None
                            else ""
                        ),
                        "Reason Code": audit.reason_code or "",
                        "Reason": audit.reason or "",
                        "Regime Confirmed": audit.regime_confirmed,
                        "BOS Present": audit.bos_present,
                        "CHOCH Present": audit.choch_present,
                        "Liquidity Present": audit.liquidity_present,
                        "Feature Count": audit.feature_count,
                        "Probability Calculated": audit.probability_calculated,
                        "Probability Accepted": audit.probability_accepted,
                        "Probability Value": self._serialize_cell(
                            audit.probability_value
                        ),
                        "Trade Quality Calculated": (
                            audit.trade_quality_calculated
                        ),
                        "Trade Quality Approved": audit.trade_quality_approved,
                        "Trade Quality Score": self._serialize_cell(
                            audit.trade_quality_score
                        ),
                        "Confluence Available": audit.confluence_available,
                        "Confluence Approved": audit.confluence_approved,
                        "Confluence Score": self._serialize_cell(
                            audit.confluence_score
                        ),
                        "Signal Generated": audit.signal_generated,
                        "Risk Approved": audit.risk_approved,
                    }
                )

        return path

    def export_rejection_summary(
        self,
        audits: Sequence[PipelineObservationAudit],
    ) -> Path:
        """Export deterministic counts for accepted and rejected observations."""

        validated = self._validate_observation_audits(audits)
        by_reason: dict[str, int] = {}
        by_stage: dict[str, int] = {}
        by_disposition: dict[str, int] = {}

        for audit in validated:
            disposition = audit.disposition.value
            by_disposition[disposition] = by_disposition.get(disposition, 0) + 1

            if audit.disposition is PipelineDisposition.ACCEPTED:
                reason_key = "APPROVED"
                stage_key = "APPROVED"
            else:
                reason_key = audit.reason_code or audit.disposition.value
                stage_key = (
                    audit.rejection_stage.value
                    if audit.rejection_stage is not None
                    else audit.stage_reached.value
                )

            by_reason[reason_key] = by_reason.get(reason_key, 0) + 1
            by_stage[stage_key] = by_stage.get(stage_key, 0) + 1

        payload = {
            "total_observations": len(validated),
            "accepted_observations": sum(
                1 for audit in validated if audit.accepted
            ),
            "rejected_observations": sum(
                1
                for audit in validated
                if audit.disposition is PipelineDisposition.REJECTED
            ),
            "disposition_counts": dict(sorted(by_disposition.items())),
            "rejection_stage_counts": dict(sorted(by_stage.items())),
            "reason_code_counts": dict(sorted(by_reason.items())),
        }

        path = self.output_directory / "rejection_summary.json"
        self._write_json(path, payload)
        return path

    @staticmethod
    def _validate_observation_audits(
        audits: Sequence[PipelineObservationAudit],
    ) -> tuple[PipelineObservationAudit, ...]:
        if isinstance(audits, (str, bytes, bytearray)) or not isinstance(
            audits, Sequence
        ):
            raise TypeError("audits must be a sequence")

        validated: list[PipelineObservationAudit] = []
        previous_timestamp: datetime | None = None
        for audit in audits:
            if not isinstance(audit, PipelineObservationAudit):
                raise TypeError(
                    "audits must contain PipelineObservationAudit values"
                )
            if (
                previous_timestamp is not None
                and audit.timestamp <= previous_timestamp
            ):
                raise ValueError(
                    "audit timestamps must be strictly increasing"
                )
            validated.append(audit)
            previous_timestamp = audit.timestamp

        return tuple(validated)

    def export_strategy_comparison_summary(
        self,
        comparison: BacktestStrategyComparison,
    ) -> Path:
        """Export deterministic pipeline-versus-strategy summary data."""

        if not isinstance(comparison, BacktestStrategyComparison):
            raise TypeError(
                "comparison must be BacktestStrategyComparison"
            )

        payload = {
            "pipeline_observation_count": (
                comparison.pipeline_observation_count
            ),
            "pipeline_approval_count": comparison.pipeline_approval_count,
            "executed_trade_count": comparison.executed_trade_count,
            "strategy_observation_count": (
                comparison.strategy_observation_count
            ),
            "strategy_setup_count": comparison.strategy_setup_count,
            "strategy_candidate_count": comparison.strategy_candidate_count,
            "pipeline_reason_counts": dict(
                comparison.pipeline_reason_counts
            ),
            "strategy_reason_counts": dict(
                comparison.strategy_reason_counts
            ),
        }

        path = (
            self.output_directory
            / "strategy_comparison_summary.json"
        )
        self._write_json(path, payload)
        return path

    def export_strategy_comparison_events(
        self,
        comparison: BacktestStrategyComparison,
    ) -> Path:
        """Export the chronological comparison event timeline."""

        if not isinstance(comparison, BacktestStrategyComparison):
            raise TypeError(
                "comparison must be BacktestStrategyComparison"
            )

        path = (
            self.output_directory
            / "strategy_comparison_events.csv"
        )
        fieldnames = (
            "Event Number",
            "Timestamp",
            "Source",
            "Event Type",
            "Direction",
            "Identifier",
        )

        with path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=list(fieldnames),
                extrasaction="raise",
            )
            writer.writeheader()

            for index, event in enumerate(
                comparison.events,
                start=1,
            ):
                writer.writerow(
                    {
                        "Event Number": index,
                        "Timestamp": event.timestamp.isoformat(),
                        "Source": event.source,
                        "Event Type": event.event_type,
                        "Direction": event.direction or "",
                        "Identifier": event.identifier or "",
                    }
                )

        return path

    def export_strategy_setup_lifecycles(
        self,
        comparison: BacktestStrategyComparison,
    ) -> Path:
        """Export one deterministic row per detected observational setup."""

        if not isinstance(comparison, BacktestStrategyComparison):
            raise TypeError("comparison must be BacktestStrategyComparison")

        path = self.output_directory / "strategy_setup_lifecycles.csv"
        fieldnames = (
            "Setup Number",
            "Setup ID",
            "Strategy ID",
            "Direction",
            "Detected At",
            "Expires At",
            "Active Observation Count",
            "No M5 Event Count",
            "Stale M5 Event Count",
            "Direction Mismatch Count",
            "Index Mismatch Count",
            "Invalid Trade Geometry Count",
            "Candidate Created",
            "Candidate Created At",
            "Terminal Status",
            "Terminal Timestamp",
        )

        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=list(fieldnames),
                extrasaction="raise",
            )
            writer.writeheader()
            for index, lifecycle in enumerate(
                comparison.setup_lifecycles,
                start=1,
            ):
                writer.writerow(
                    {
                        "Setup Number": index,
                        "Setup ID": lifecycle.setup_id,
                        "Strategy ID": lifecycle.strategy_id,
                        "Direction": lifecycle.direction,
                        "Detected At": lifecycle.detected_at.isoformat(),
                        "Expires At": lifecycle.expires_at.isoformat(),
                        "Active Observation Count": lifecycle.active_observation_count,
                        "No M5 Event Count": lifecycle.no_m5_event_count,
                        "Stale M5 Event Count": lifecycle.stale_m5_event_count,
                        "Direction Mismatch Count": lifecycle.direction_mismatch_count,
                        "Index Mismatch Count": lifecycle.index_mismatch_count,
                        "Invalid Trade Geometry Count": lifecycle.invalid_trade_geometry_count,
                        "Candidate Created": lifecycle.candidate_created,
                        "Candidate Created At": (
                            lifecycle.candidate_created_at.isoformat()
                            if lifecycle.candidate_created_at is not None
                            else ""
                        ),
                        "Terminal Status": lifecycle.terminal_status,
                        "Terminal Timestamp": (
                            lifecycle.terminal_timestamp.isoformat()
                            if lifecycle.terminal_timestamp is not None
                            else ""
                        ),
                    }
                )

        return path

    def export_strategy_post_expiry_triggers(
        self,
        comparison: BacktestStrategyComparison,
    ) -> Path:
        if not isinstance(comparison, BacktestStrategyComparison):
            raise TypeError("comparison must be BacktestStrategyComparison")

        path = self.output_directory / "strategy_post_expiry_triggers.csv"
        fieldnames = (
            "Setup Number", "Setup ID", "Strategy ID", "Direction",
            "Expired At", "Maximum Bars", "Bars Observed",
            "Trigger Found", "First Trigger At", "Bars After Expiry",
            "Trigger Type", "Window Complete",
            "Geometry Valid", "Trigger Price",
            "Invalidation Price", "Stop Reference Price",
            "Target Reference Prices", "Nearest Target Price",
            "Target Directionally Valid At Trigger",
            "Target Crossed Before Trigger",
            "First Target Crossed At", "Bars Since Target Cross",
            "Target Distance At First Post Expiry Bar",
            "Target Distance At Trigger",
            "Hypothetical Terminal Reason",
            "Hypothetical Terminal At",
            "Bars After Expiry At Hypothetical Terminal",
            "Setup Age Minutes At Hypothetical Terminal",
            "Trigger Appeared After Hypothetical Terminal",
            "Candidate Created After Hypothetical Terminal",
            "Bars From Hypothetical Terminal To Trigger",
            "Geometry Rejection Code", "Geometry Rejection Reason",
            "Entry Price", "Stop Loss Price",
            "Take Profit Prices", "Reward Risk", "Outcome",
            "Outcome Timestamp", "Outcome Bars Evaluated",
            "Maximum Favorable R Multiple",
            "Maximum Adverse R Multiple",
            "Outcome Window Complete",
        )
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=list(fieldnames),
                extrasaction="raise",
            )
            writer.writeheader()
            for index, record in enumerate(
                comparison.post_expiry_triggers,
                start=1,
            ):
                writer.writerow(
                    {
                        "Setup Number": index,
                        "Setup ID": record.setup_id,
                        "Strategy ID": record.strategy_id,
                        "Direction": record.direction,
                        "Expired At": record.expired_at.isoformat(),
                        "Maximum Bars": record.maximum_bars,
                        "Bars Observed": record.bars_observed,
                        "Trigger Found": record.trigger_found,
                        "First Trigger At": (
                            record.first_trigger_at.isoformat()
                            if record.first_trigger_at
                            else ""
                        ),
                        "Bars After Expiry": (
                            record.bars_after_expiry
                            if record.bars_after_expiry is not None
                            else ""
                        ),
                        "Trigger Type": record.trigger_type or "",
                        "Window Complete": record.window_complete,
                        "Geometry Valid": (
                            record.geometry_valid
                            if record.geometry_valid is not None
                            else ""
                        ),
                        "Trigger Price": (
                            record.trigger_price
                            if record.trigger_price is not None
                            else ""
                        ),
                        "Invalidation Price": (
                            record.invalidation_price
                            if record.invalidation_price is not None
                            else ""
                        ),
                        "Stop Reference Price": (
                            record.stop_reference_price
                            if record.stop_reference_price is not None
                            else ""
                        ),
                        "Target Reference Prices": json.dumps(
                            record.target_reference_prices
                        ),
                        "Nearest Target Price": (
                            record.nearest_target_price
                            if record.nearest_target_price is not None
                            else ""
                        ),
                        "Target Directionally Valid At Trigger": (
                            record.target_directionally_valid_at_trigger
                            if record.target_directionally_valid_at_trigger
                            is not None
                            else ""
                        ),
                        "Target Crossed Before Trigger": (
                            record.target_crossed_before_trigger
                        ),
                        "First Target Crossed At": (
                            record.first_target_crossed_at.isoformat()
                            if record.first_target_crossed_at is not None
                            else ""
                        ),
                        "Bars Since Target Cross": (
                            record.bars_since_target_cross
                            if record.bars_since_target_cross is not None
                            else ""
                        ),
                        "Target Distance At First Post Expiry Bar": (
                            record.target_distance_at_first_post_expiry_bar
                            if record.target_distance_at_first_post_expiry_bar
                            is not None
                            else ""
                        ),
                        "Target Distance At Trigger": (
                            record.target_distance_at_trigger
                            if record.target_distance_at_trigger is not None
                            else ""
                        ),
                        "Hypothetical Terminal Reason": (
                            record.hypothetical_terminal_reason or ""
                        ),
                        "Hypothetical Terminal At": (
                            record.hypothetical_terminal_at.isoformat()
                            if record.hypothetical_terminal_at is not None
                            else ""
                        ),
                        "Bars After Expiry At Hypothetical Terminal": (
                            record.bars_after_expiry_at_hypothetical_terminal
                            if record.bars_after_expiry_at_hypothetical_terminal
                            is not None
                            else ""
                        ),
                        "Setup Age Minutes At Hypothetical Terminal": (
                            record.setup_age_minutes_at_hypothetical_terminal
                            if record.setup_age_minutes_at_hypothetical_terminal
                            is not None
                            else ""
                        ),
                        "Trigger Appeared After Hypothetical Terminal": (
                            record.trigger_appeared_after_hypothetical_terminal
                        ),
                        "Candidate Created After Hypothetical Terminal": (
                            record.candidate_created_after_hypothetical_terminal
                        ),
                        "Bars From Hypothetical Terminal To Trigger": (
                            record.bars_from_hypothetical_terminal_to_trigger
                            if record.bars_from_hypothetical_terminal_to_trigger
                            is not None
                            else ""
                        ),
                        "Geometry Rejection Code": (
                            record.geometry_rejection_code or ""
                        ),
                        "Geometry Rejection Reason": (
                            record.geometry_rejection_reason or ""
                        ),
                        "Entry Price": (
                            record.entry_price
                            if record.entry_price is not None
                            else ""
                        ),
                        "Stop Loss Price": (
                            record.stop_loss_price
                            if record.stop_loss_price is not None
                            else ""
                        ),
                        "Take Profit Prices": json.dumps(
                            record.take_profit_prices
                        ),
                        "Reward Risk": (
                            record.reward_risk
                            if record.reward_risk is not None
                            else ""
                        ),
                        "Outcome": record.outcome or "",
                        "Outcome Timestamp": (
                            record.outcome_timestamp.isoformat()
                            if record.outcome_timestamp is not None
                            else ""
                        ),
                        "Outcome Bars Evaluated": record.outcome_bars_evaluated,
                        "Maximum Favorable R Multiple": (
                            record.maximum_favorable_r_multiple
                            if record.maximum_favorable_r_multiple is not None
                            else ""
                        ),
                        "Maximum Adverse R Multiple": (
                            record.maximum_adverse_r_multiple
                            if record.maximum_adverse_r_multiple is not None
                            else ""
                        ),
                        "Outcome Window Complete": record.outcome_window_complete,
                    }
                )
        return path

    def export_equity_curve(
        self,
        result: BacktestResult,
        initial_balance: float,
    ) -> Path:
        """Export ``equity_curve.csv`` using realized net P&L."""

        if not math.isfinite(initial_balance):
            raise ValueError("initial_balance must be finite")

        path = self.output_directory / "equity_curve.csv"
        balance = initial_balance

        with path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as file:
            writer = csv.writer(file)
            writer.writerow(["Trade", "Balance"])
            writer.writerow([0, balance])

            for index, trade in enumerate(result.trades, start=1):
                balance += trade.net_profit
                writer.writerow([index, balance])

        return path

    def export_statistics(
        self,
        statistics: dict,
        *,
        execution_model_provenance: Mapping[str, object] | None = None,
    ) -> Path:
        """Export JSON-safe ``statistics.json`` with execution provenance."""

        payload: dict[str, object] = dict(statistics)
        self._attach_execution_model_provenance(
            payload,
            execution_model_provenance,
        )
        path = self.output_directory / "statistics.json"
        self._write_json(path, payload)
        return path

    def _build_trade_row(
        self,
        *,
        trade_number: int,
        trade: BacktestTrade,
        metadata: dict[str, Any],
        extra_keys: Sequence[str],
    ) -> dict[str, Any]:
        row: dict[str, Any] = {
            "Trade Number": trade_number,
            "Entry Time": self._serialize_cell(trade.entry_time),
            "Exit Time": self._serialize_cell(trade.exit_time),
            "Direction": self._serialize_cell(trade.direction),
            "Outcome": self._serialize_cell(trade.outcome),
            "Exit Reason": self._serialize_cell(trade.exit_reason),
            "Entry Price": trade.entry_price,
            "Exit Price": trade.exit_price,
            "Position Size": trade.position_size,
            "Spread Cost": trade.spread_cost,
            "Commission": trade.commission,
            "Gross Profit": trade.gross_profit,
            "Net Profit": trade.net_profit,
            "Holding Bars": trade.holding_bars,
            "Holding Time": str(trade.holding_time),
            "Holding Seconds": trade.holding_time.total_seconds(),
            "Risk Reward": trade.risk_reward,
            "Maximum Favorable Excursion": trade.max_favorable_excursion,
            "Maximum Adverse Excursion": trade.max_adverse_excursion,
            "Highest Price": trade.highest_price,
            "Lowest Price": trade.lowest_price,
            "Breakeven Triggered": trade.breakeven_triggered,
            "Trailing Stop Triggered": trade.trailing_stop_triggered,
            "Partial Exit Taken": trade.partial_exit_taken,
            "Lifecycle Events": self._serialize_cell(trade.lifecycle_events),
        }

        for heading, key in self._METADATA_COLUMNS:
            row[heading] = self._serialize_cell(metadata.get(key))

        for key in extra_keys:
            row[f"Metadata:{key}"] = self._serialize_cell(metadata.get(key))

        row["Metadata JSON"] = json.dumps(
            self._to_json_compatible(trade.metadata),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return row

    @classmethod
    def _flatten_metadata(
        cls,
        metadata: Mapping[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(metadata, Mapping):
            raise TypeError("trade metadata must be a mapping")

        flattened: dict[str, Any] = {}
        cls._flatten_mapping(
            metadata,
            destination=flattened,
            prefix="",
            active_ids=set(),
        )
        return flattened

    @classmethod
    def _flatten_mapping(
        cls,
        mapping: Mapping[Any, Any],
        *,
        destination: dict[str, Any],
        prefix: str,
        active_ids: set[int],
    ) -> None:
        mapping_id = id(mapping)
        if mapping_id in active_ids:
            if prefix:
                destination[prefix] = "<recursive>"
            return

        active_ids.add(mapping_id)
        try:
            for raw_key in sorted(mapping, key=lambda key: str(key)):
                key = str(raw_key)
                path = f"{prefix}.{key}" if prefix else key
                value = mapping[raw_key]
                if isinstance(value, Mapping):
                    cls._flatten_mapping(
                        value,
                        destination=destination,
                        prefix=path,
                        active_ids=active_ids,
                    )
                else:
                    destination[path] = value
        finally:
            active_ids.remove(mapping_id)

    @classmethod
    def _write_json(
        cls,
        path: Path,
        payload: Any,
    ) -> None:
        with path.open("w", encoding="utf-8") as file:
            json.dump(
                cls._to_json_compatible(payload),
                file,
                indent=4,
                ensure_ascii=False,
                sort_keys=True,
                allow_nan=False,
            )

    @classmethod
    def _serialize_cell(cls, value: Any) -> Any:
        if value is None:
            return ""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            if isinstance(value, float):
                if math.isnan(value):
                    raise ValueError("CSV export does not permit NaN values")
                if math.isinf(value):
                    return "Infinity" if value > 0.0 else "-Infinity"
            return value
        if isinstance(value, (str, datetime, date, timedelta, Enum)):
            converted = cls._to_json_compatible(value)
            return (
                converted
                if not isinstance(converted, (dict, list))
                else json.dumps(
                    converted,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        converted = cls._to_json_compatible(value)
        if isinstance(converted, (dict, list)):
            return json.dumps(
                converted,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        return converted

    @classmethod
    def _to_json_compatible(
        cls,
        value: Any,
        *,
        active_ids: set[int] | None = None,
    ) -> Any:
        if active_ids is None:
            active_ids = set()

        if value is None or isinstance(value, (str, bool, int)):
            return value
        if isinstance(value, float):
            if math.isnan(value):
                raise ValueError("JSON export does not permit NaN values")
            if math.isinf(value):
                return "Infinity" if value > 0.0 else "-Infinity"
            return value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, timedelta):
            return value.total_seconds()
        if isinstance(value, Enum):
            return cls._to_json_compatible(value.value, active_ids=active_ids)

        value_id = id(value)
        if isinstance(value, Mapping):
            if value_id in active_ids:
                return "<recursive>"
            active_ids.add(value_id)
            try:
                return {
                    str(key): cls._to_json_compatible(
                        item,
                        active_ids=active_ids,
                    )
                    for key, item in sorted(
                        value.items(),
                        key=lambda pair: str(pair[0]),
                    )
                }
            finally:
                active_ids.remove(value_id)

        if isinstance(value, Sequence) and not isinstance(
            value,
            (str, bytes, bytearray),
        ):
            if value_id in active_ids:
                return "<recursive>"
            active_ids.add(value_id)
            try:
                return [
                    cls._to_json_compatible(item, active_ids=active_ids)
                    for item in value
                ]
            finally:
                active_ids.remove(value_id)

        return str(value)

    @classmethod
    def _attach_execution_model_provenance(
        cls,
        payload: dict[str, object],
        provenance: Mapping[str, object] | None,
    ) -> None:
        if provenance is None:
            return
        if not isinstance(provenance, Mapping):
            raise TypeError("execution_model_provenance must be a mapping or None")
        normalized = cls._to_json_compatible(dict(provenance))
        if not isinstance(normalized, dict):
            raise TypeError("execution model provenance must serialize to a mapping")
        model_id = normalized.get("execution_model_id")
        if not isinstance(model_id, str) or not model_id:
            raise ValueError("execution model provenance requires execution_model_id")
        payload["execution_model_id"] = model_id
        payload["execution_model"] = normalized
