"""Alignment-integrity diagnostics for Variant B shadow integration."""

from __future__ import annotations

import csv
import json
from bisect import bisect_left
from collections import Counter, defaultdict
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


class MethodologyVariantBAlignmentIntegrity:
    """Separate strict exact alignment from exploratory forward alignment."""

    VARIANT: Final[str] = (
        "VARIANT_B_BEARISH_EXCLUDE_COMPATIBLE_SWEEP"
    )
    STOP_ATR_MULTIPLE: Final[float] = 1.0
    TARGET_R: Final[float] = 2.0
    MAXIMUM_FORWARD_LAG_MINUTES: Final[int] = 15

    _CSV_COLUMNS: Final[tuple[str, ...]] = (
        "Variant",
        "Comparison Dataset",
        "Lag Bucket",
        "Shadow Observation Timestamp",
        "Active Audit Timestamp",
        "Audit Reuse Count",
        "Active Accepted",
        "Active Disposition",
        "Active Stage Reached",
        "Active Rejection Stage",
        "Active Reason Code",
        "Shadow Result R",
        "Shadow Exit Reason",
        "Shadow Holding Bars",
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
            / "methodology_variant_b_alignment_integrity.csv"
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
            / "methodology_variant_b_alignment_integrity.json"
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
        audits_tuple = tuple(sorted(audits, key=lambda item: item.timestamp))
        self._validate_audits(audits_tuple)

        _, matrix_results = self.matrix.calculate(
            observations_tuple,
            m5_bars,
            window_metadata=window_metadata,
        )
        shadow_results = tuple(
            result
            for result in matrix_results
            if result.stop_atr_multiple == self.STOP_ATR_MULTIPLE
            and result.target_r == self.TARGET_R
        )

        context_by_timestamp = {
            item.timestamp.astimezone(UTC): item
            for item in observations_tuple
        }
        audit_by_timestamp = {
            audit.timestamp.astimezone(UTC): audit
            for audit in audits_tuple
        }
        audit_timestamps = tuple(sorted(audit_by_timestamp))

        alignments: list[
            tuple[
                VariantBATRShadowResult,
                PipelineObservationAudit | None,
                str,
            ]
        ] = []
        for result in shadow_results:
            observation_timestamp = (
                result.observation_timestamp.astimezone(UTC)
            )
            exact = audit_by_timestamp.get(observation_timestamp)
            if exact is not None:
                alignments.append((result, exact, "0_MINUTES"))
                continue

            index = bisect_left(audit_timestamps, observation_timestamp)
            if index >= len(audit_timestamps):
                alignments.append((result, None, "UNMATCHED"))
                continue

            audit_timestamp = audit_timestamps[index]
            lag = (
                audit_timestamp - observation_timestamp
            ).total_seconds() / 60.0
            if lag < 0.0 or lag > self.MAXIMUM_FORWARD_LAG_MINUTES:
                alignments.append((result, None, "UNMATCHED"))
                continue

            bucket = (
                "5_MINUTES"
                if lag <= 5.0
                else "10_MINUTES"
                if lag <= 10.0
                else "15_MINUTES"
            )
            alignments.append(
                (result, audit_by_timestamp[audit_timestamp], bucket)
            )

        reuse_counts: Counter[datetime] = Counter(
            audit.timestamp.astimezone(UTC)
            for _, audit, _ in alignments
            if audit is not None
        )

        rows: list[dict[str, object]] = []
        for result, audit, lag_bucket in alignments:
            dataset = (
                "STRICT_EXACT_COMPARISON"
                if lag_bucket == "0_MINUTES"
                else "EXPLORATORY_FORWARD_COMPARISON"
                if audit is not None
                else "UNMATCHED"
            )
            observation = context_by_timestamp.get(
                result.observation_timestamp.astimezone(UTC)
            )
            rows.append(
                {
                    "Variant": self.VARIANT,
                    "Comparison Dataset": dataset,
                    "Lag Bucket": lag_bucket,
                    "Shadow Observation Timestamp": (
                        result.observation_timestamp.isoformat()
                    ),
                    "Active Audit Timestamp": (
                        audit.timestamp.isoformat()
                        if audit is not None
                        else ""
                    ),
                    "Audit Reuse Count": (
                        reuse_counts[
                            audit.timestamp.astimezone(UTC)
                        ]
                        if audit is not None
                        else 0
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
                    "Shadow Result R": result.result_r,
                    "Shadow Exit Reason": result.exit_reason,
                    "Shadow Holding Bars": result.holding_bars,
                    "Session": (
                        observation.context.session_name
                        if observation is not None
                        else result.session
                    ),
                    "Regime": (
                        observation.context.regime_name
                        if observation is not None
                        else result.regime
                    ),
                }
            )

        strict_rows = [
            row
            for row in rows
            if row["Comparison Dataset"] == "STRICT_EXACT_COMPARISON"
        ]
        forward_rows = [
            row
            for row in rows
            if row["Comparison Dataset"]
            == "EXPLORATORY_FORWARD_COMPARISON"
        ]
        unmatched_rows = [
            row
            for row in rows
            if row["Comparison Dataset"] == "UNMATCHED"
        ]

        bucket_summaries = {
            bucket: self._summarize_rows(
                [row for row in rows if row["Lag Bucket"] == bucket]
            )
            for bucket in (
                "0_MINUTES",
                "5_MINUTES",
                "10_MINUTES",
                "15_MINUTES",
                "UNMATCHED",
            )
        }

        reused_audits = {
            timestamp.isoformat(): count
            for timestamp, count in sorted(reuse_counts.items())
            if count > 1
        }

        payload = {
            "variant": self.VARIANT,
            "frozen_shadow_plan": {
                "entry_policy": "FIRST_AVAILABLE_WHILE_FLAT",
                "stop_atr_multiple": self.STOP_ATR_MULTIPLE,
                "target_r": self.TARGET_R,
                "maximum_holding_bars": self.matrix.HORIZON_BARS,
            },
            "comparison_datasets": {
                "STRICT_EXACT_COMPARISON": (
                    "Only identical shadow-observation and active-audit "
                    "timestamps. This is the only dataset permitted for "
                    "active-gate conclusions."
                ),
                "EXPLORATORY_FORWARD_COMPARISON": (
                    "Nearest future audit within 15 minutes. Exploratory "
                    "only; not valid for changing active gates."
                ),
            },
            "counts": {
                "shadow_trade_count": len(shadow_results),
                "strict_exact_count": len(strict_rows),
                "exploratory_forward_count": len(forward_rows),
                "unmatched_count": len(unmatched_rows),
                "unique_matched_audit_count": len(reuse_counts),
                "reused_audit_timestamp_count": len(reused_audits),
                "shadow_rows_using_reused_audits": sum(
                    row["Audit Reuse Count"] > 1
                    for row in rows
                    if row["Active Audit Timestamp"]
                ),
            },
            "audit_timestamp_integrity": {
                "audit_count": len(audits_tuple),
                "unique_audit_timestamp_count": len(audit_by_timestamp),
                "duplicate_audit_timestamp_count": (
                    len(audits_tuple) - len(audit_by_timestamp)
                ),
                "reused_audits": reused_audits,
            },
            "lag_bucket_summaries": bucket_summaries,
            "strict_exact_rejection_stage_counts": self._counter(
                strict_rows,
                "Active Rejection Stage",
            ),
            "strict_exact_rejection_code_counts": self._counter(
                strict_rows,
                "Active Reason Code",
            ),
            "exploratory_forward_rejection_stage_counts": self._counter(
                forward_rows,
                "Active Rejection Stage",
            ),
            "exploratory_forward_rejection_code_counts": self._counter(
                forward_rows,
                "Active Reason Code",
            ),
            "decision_rule": {
                "active_gate_changes_permitted_from": (
                    "STRICT_EXACT_COMPARISON_ONLY"
                ),
                "active_gate_changes_currently_approved": False,
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

    def _summarize_rows(
        self,
        rows: Sequence[Mapping[str, object]],
    ) -> dict[str, object]:
        values = [
            float(row["Shadow Result R"])
            for row in rows
        ]
        accepted = sum(
            row["Active Accepted"] is True
            for row in rows
        )
        return {
            "row_count": len(rows),
            "average_shadow_r": (
                mean(values) if values else None
            ),
            "total_shadow_r": sum(values),
            "positive_shadow_trade_rate": (
                sum(value > 0.0 for value in values) / len(values)
                if values
                else None
            ),
            "active_accepted_count": accepted,
            "active_acceptance_rate": (
                accepted / len(rows) if rows else None
            ),
            "rejection_stage_counts": self._counter(
                rows,
                "Active Rejection Stage",
            ),
            "rejection_code_counts": self._counter(
                rows,
                "Active Reason Code",
            ),
        }

    @staticmethod
    def _counter(
        rows: Sequence[Mapping[str, object]],
        key: str,
    ) -> dict[str, int]:
        counts = Counter(
            str(row[key])
            for row in rows
            if row.get(key)
        )
        return dict(sorted(counts.items()))

    @staticmethod
    def _validate_audits(
        audits: tuple[PipelineObservationAudit, ...],
    ) -> None:
        for audit in audits:
            if not isinstance(audit, PipelineObservationAudit):
                raise TypeError(
                    "audits must contain PipelineObservationAudit"
                )
