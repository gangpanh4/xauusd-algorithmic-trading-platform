"""Observational Variant B shadow integration with active pipeline audits."""

from __future__ import annotations

import csv
import json
from bisect import bisect_left
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Final

from core.trading_pipeline.models import PipelineObservationAudit

from .methodology_observer import MethodologyObservation
from .methodology_variant_b_atr_shadow_matrix import (
    MethodologyVariantBATRShadowMatrix,
    VariantBATRShadowResult,
)


class MethodologyVariantBShadowIntegration:
    """Compare the frozen executable shadow plan with active audit facts."""

    VARIANT: Final[str] = (
        "VARIANT_B_BEARISH_EXCLUDE_COMPATIBLE_SWEEP"
    )
    STOP_ATR_MULTIPLE: Final[float] = 1.0
    TARGET_R: Final[float] = 2.0
    MAXIMUM_ALIGNMENT_LAG_MINUTES: Final[int] = 15

    _CSV_COLUMNS: Final[tuple[str, ...]] = (
        "Variant",
        "Observation Timestamp",
        "Entry Timestamp",
        "Exit Timestamp",
        "Alignment Method",
        "Alignment Lag Minutes",
        "Shadow Direction",
        "Shadow Entry Policy",
        "Shadow Entry Price",
        "Shadow ATR 14",
        "Shadow Stop ATR Multiple",
        "Shadow Stop Price",
        "Shadow Target R",
        "Shadow Target Price",
        "Shadow Exit Reason",
        "Shadow Result R",
        "Shadow Holding Bars",
        "Shadow Same Candle Ambiguity",
        "Active Audit Matched",
        "Active Audit Timestamp",
        "Active Accepted",
        "Active Disposition",
        "Active Stage Reached",
        "Active Rejection Stage",
        "Active Reason Code",
        "Active Reason",
        "Active Probability Calculated",
        "Active Probability Accepted",
        "Active Probability Value",
        "Active Trade Quality Calculated",
        "Active Trade Quality Approved",
        "Active Trade Quality Score",
        "Active Confluence Available",
        "Active Confluence Approved",
        "Active Confluence Score",
        "Active Signal Generated",
        "Active Risk Approved",
        "Comparison Classification",
        "Session",
        "Regime",
    )

    def __init__(
        self,
        output_directory: str | Path = "output/backtests",
    ) -> None:
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.matrix = MethodologyVariantBATRShadowMatrix(
            output_directory
        )

    def export(
        self,
        observations: Sequence[MethodologyObservation],
        audits: Sequence[PipelineObservationAudit],
        m5_bars: Sequence[object],
        *,
        window_metadata: Mapping[str, object] | None = None,
    ) -> tuple[Path, Path]:
        payload, rows = self.calculate(
            observations,
            audits,
            m5_bars,
            window_metadata=window_metadata,
        )

        csv_path = (
            self.output_directory
            / "methodology_variant_b_shadow_integration.csv"
        )
        with csv_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=list(self._CSV_COLUMNS),
                extrasaction="raise",
            )
            writer.writeheader()
            writer.writerows(rows)

        json_path = (
            self.output_directory
            / "methodology_variant_b_shadow_integration.json"
        )
        json_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return csv_path, json_path

    def calculate(
        self,
        observations: Sequence[MethodologyObservation],
        audits: Sequence[PipelineObservationAudit],
        m5_bars: Sequence[object],
        *,
        window_metadata: Mapping[str, object] | None = None,
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        observations_tuple = tuple(observations)
        audits_tuple = tuple(
            sorted(audits, key=lambda item: item.timestamp)
        )
        self._validate_audits(audits_tuple)

        _, matrix_results = self.matrix.calculate(
            observations_tuple,
            m5_bars,
            window_metadata=window_metadata,
        )
        shadow_results = tuple(
            item
            for item in matrix_results
            if item.stop_atr_multiple == self.STOP_ATR_MULTIPLE
            and item.target_r == self.TARGET_R
        )

        observation_context = {
            item.timestamp.astimezone(UTC): item
            for item in observations_tuple
        }
        audit_timestamps = tuple(
            item.timestamp.astimezone(UTC)
            for item in audits_tuple
        )

        rows: list[dict[str, object]] = []
        unmatched: list[str] = []
        classifications: Counter[str] = Counter()
        rejection_stages: Counter[str] = Counter()
        rejection_codes: Counter[str] = Counter()
        alignment_methods: Counter[str] = Counter()

        for result in shadow_results:
            audit, method, lag_minutes = self._align_audit(
                result.observation_timestamp,
                audits_tuple,
                audit_timestamps,
            )
            context = observation_context.get(
                result.observation_timestamp.astimezone(UTC)
            )

            if audit is None:
                unmatched.append(
                    result.observation_timestamp.isoformat()
                )
                classification = "SHADOW_ONLY_NO_ACTIVE_AUDIT"
            elif audit.accepted:
                classification = "SHADOW_AND_ACTIVE_ACCEPTED"
            else:
                classification = "SHADOW_ELIGIBLE_ACTIVE_REJECTED"
                if audit.rejection_stage is not None:
                    rejection_stages[audit.rejection_stage.value] += 1
                if audit.reason_code:
                    rejection_codes[audit.reason_code] += 1

            classifications[classification] += 1
            alignment_methods[method] += 1

            rows.append(
                self._row(
                    result=result,
                    audit=audit,
                    alignment_method=method,
                    alignment_lag_minutes=lag_minutes,
                    classification=classification,
                    session=(
                        context.context.session_name
                        if context is not None
                        else result.session
                    ),
                    regime=(
                        context.context.regime_name
                        if context is not None
                        else result.regime
                    ),
                )
            )

        active_accepted_count = sum(
            audit.accepted for audit in audits_tuple
        )
        matched_rows = [
            row for row in rows if row["Active Audit Matched"]
        ]
        accepted_shadow_rows = [
            row for row in matched_rows if row["Active Accepted"]
        ]

        payload = {
            "variant": self.VARIANT,
            "frozen_shadow_plan": {
                "direction": "BEARISH",
                "entry_policy": "FIRST_AVAILABLE_WHILE_FLAT",
                "entry_price": "NEXT_COMPLETED_M5_BAR_OPEN",
                "atr_period": self.matrix.ATR_PERIOD,
                "stop_atr_multiple": self.STOP_ATR_MULTIPLE,
                "target_r": self.TARGET_R,
                "maximum_holding_bars": self.matrix.HORIZON_BARS,
                "same_candle_policy": (
                    "AMBIGUOUS_AND_CONSERVATIVE_STOP_FIRST"
                ),
            },
            "counts": {
                "methodology_observation_count": len(
                    observations_tuple
                ),
                "active_audit_count": len(audits_tuple),
                "active_accepted_audit_count": active_accepted_count,
                "executed_shadow_trade_count": len(shadow_results),
                "matched_shadow_trade_count": len(matched_rows),
                "unmatched_shadow_trade_count": len(unmatched),
                "shadow_and_active_accepted_count": len(
                    accepted_shadow_rows
                ),
                "shadow_active_acceptance_rate": (
                    len(accepted_shadow_rows) / len(matched_rows)
                    if matched_rows
                    else None
                ),
            },
            "comparison_classification_counts": dict(
                sorted(classifications.items())
            ),
            "active_rejection_stage_counts_for_shadow": dict(
                sorted(rejection_stages.items())
            ),
            "active_rejection_code_counts_for_shadow": dict(
                sorted(rejection_codes.items())
            ),
            "alignment": {
                "policy": "EXACT_OR_ASOF_FORWARD",
                "anchor": "SHADOW_OBSERVATION_TIMESTAMP",
                "maximum_lag_minutes": (
                    self.MAXIMUM_ALIGNMENT_LAG_MINUTES
                ),
                "method_counts": dict(
                    sorted(alignment_methods.items())
                ),
                "unmatched_observation_timestamps": unmatched,
            },
            "shadow_performance_reference": {
                "average_r": (
                    mean(
                        result.result_r
                        for result in shadow_results
                    )
                    if shadow_results
                    else None
                ),
                "total_r": sum(
                    result.result_r
                    for result in shadow_results
                ),
                "positive_trade_rate": (
                    sum(
                        result.result_r > 0.0
                        for result in shadow_results
                    )
                    / len(shadow_results)
                    if shadow_results
                    else None
                ),
            },
            "backtest_live_parity_readiness": {
                "status": "NOT_READY",
                "closed_candle_candidate_definition": "AVAILABLE",
                "pre_entry_atr_stop_calculation": "AVAILABLE",
                "deterministic_next_bar_entry": "AVAILABLE",
                "active_pipeline_audit_comparison": "AVAILABLE",
                "active_trade_authority": "DISABLED",
                "live_shadow_state_machine": "NOT_IMPLEMENTED",
                "historical_bid_ask_spread_at_entry": "UNAVAILABLE",
                "broker_order_validation": "NOT_IMPLEMENTED",
                "position_reconciliation": "NOT_IMPLEMENTED",
                "restart_recovery": "NOT_IMPLEMENTED",
            },
            "window_metadata": dict(window_metadata or {}),
            "observational_only": True,
            "trade_authority": False,
            "signal_authority": False,
            "approval_authority": False,
            "position_sizing_authority": False,
            "order_creation_authority": False,
            "active_decision_modified": False,
            "active_pipeline_modified": False,
            "future_information_used_for_research_only": True,
        }
        return payload, rows

    def _align_audit(
        self,
        observation_timestamp: datetime,
        audits: tuple[PipelineObservationAudit, ...],
        audit_timestamps: tuple[datetime, ...],
    ) -> tuple[
        PipelineObservationAudit | None,
        str,
        float | None,
    ]:
        timestamp = observation_timestamp.astimezone(UTC)
        index = bisect_left(audit_timestamps, timestamp)
        if index >= len(audits):
            return None, "UNMATCHED", None

        audit = audits[index]
        audit_timestamp = audit.timestamp.astimezone(UTC)
        lag_minutes = (
            audit_timestamp - timestamp
        ).total_seconds() / 60.0
        if lag_minutes < 0.0:
            return None, "UNMATCHED", None
        if lag_minutes > self.MAXIMUM_ALIGNMENT_LAG_MINUTES:
            return None, "UNMATCHED", lag_minutes

        method = "EXACT" if lag_minutes == 0.0 else "ASOF_FORWARD"
        return audit, method, lag_minutes

    def _row(
        self,
        *,
        result: VariantBATRShadowResult,
        audit: PipelineObservationAudit | None,
        alignment_method: str,
        alignment_lag_minutes: float | None,
        classification: str,
        session: str,
        regime: str,
    ) -> dict[str, object]:
        return {
            "Variant": self.VARIANT,
            "Observation Timestamp": (
                result.observation_timestamp.isoformat()
            ),
            "Entry Timestamp": result.entry_timestamp.isoformat(),
            "Exit Timestamp": result.exit_timestamp.isoformat(),
            "Alignment Method": alignment_method,
            "Alignment Lag Minutes": alignment_lag_minutes,
            "Shadow Direction": "BEARISH",
            "Shadow Entry Policy": "FIRST_AVAILABLE_WHILE_FLAT",
            "Shadow Entry Price": result.entry_price,
            "Shadow ATR 14": result.atr_14,
            "Shadow Stop ATR Multiple": result.stop_atr_multiple,
            "Shadow Stop Price": result.stop_price,
            "Shadow Target R": result.target_r,
            "Shadow Target Price": result.target_price,
            "Shadow Exit Reason": result.exit_reason,
            "Shadow Result R": result.result_r,
            "Shadow Holding Bars": result.holding_bars,
            "Shadow Same Candle Ambiguity": (
                result.same_candle_dual_touch
            ),
            "Active Audit Matched": audit is not None,
            "Active Audit Timestamp": (
                audit.timestamp.isoformat()
                if audit is not None
                else ""
            ),
            "Active Accepted": (
                audit.accepted if audit is not None else None
            ),
            "Active Disposition": (
                audit.disposition.value
                if audit is not None
                else ""
            ),
            "Active Stage Reached": (
                audit.stage_reached.value
                if audit is not None
                else ""
            ),
            "Active Rejection Stage": (
                audit.rejection_stage.value
                if audit is not None
                and audit.rejection_stage is not None
                else ""
            ),
            "Active Reason Code": (
                audit.reason_code or ""
                if audit is not None
                else ""
            ),
            "Active Reason": (
                audit.reason or ""
                if audit is not None
                else ""
            ),
            "Active Probability Calculated": (
                audit.probability_calculated
                if audit is not None
                else None
            ),
            "Active Probability Accepted": (
                audit.probability_accepted
                if audit is not None
                else None
            ),
            "Active Probability Value": (
                audit.probability_value
                if audit is not None
                else None
            ),
            "Active Trade Quality Calculated": (
                audit.trade_quality_calculated
                if audit is not None
                else None
            ),
            "Active Trade Quality Approved": (
                audit.trade_quality_approved
                if audit is not None
                else None
            ),
            "Active Trade Quality Score": (
                audit.trade_quality_score
                if audit is not None
                else None
            ),
            "Active Confluence Available": (
                audit.confluence_available
                if audit is not None
                else None
            ),
            "Active Confluence Approved": (
                audit.confluence_approved
                if audit is not None
                else None
            ),
            "Active Confluence Score": (
                audit.confluence_score
                if audit is not None
                else None
            ),
            "Active Signal Generated": (
                audit.signal_generated
                if audit is not None
                else None
            ),
            "Active Risk Approved": (
                audit.risk_approved
                if audit is not None
                else None
            ),
            "Comparison Classification": classification,
            "Session": session,
            "Regime": regime,
        }

    @staticmethod
    def _validate_audits(
        audits: tuple[PipelineObservationAudit, ...],
    ) -> None:
        for audit in audits:
            if not isinstance(audit, PipelineObservationAudit):
                raise TypeError(
                    "audits must contain PipelineObservationAudit"
                )
        timestamps = tuple(audit.timestamp for audit in audits)
        if any(
            current < previous
            for previous, current in zip(
                timestamps,
                timestamps[1:],
            )
        ):
            raise ValueError(
                "audits must be sorted chronologically"
            )
