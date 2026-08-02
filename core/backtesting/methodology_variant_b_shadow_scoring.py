"""Observational shadow scoring for the frozen Variant B candidate."""

from __future__ import annotations

import csv
import json
from bisect import bisect_right
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

from core.strategies.methodology_models import (
    MethodologyDirection,
    MethodologyIdentifier,
)
from core.trading_pipeline.models import PipelineObservationAudit

from .methodology_observer import MethodologyObservation
from .methodology_outcome_research import MethodologyOutcomeEvaluation


class MethodologyVariantBShadowScoring:
    """Score frozen Variant B evidence without influencing trade decisions."""

    VARIANT: Final[str] = (
        "VARIANT_B_BEARISH_EXCLUDE_COMPATIBLE_SWEEP"
    )
    HORIZON_BARS: Final[int] = 24
    MAXIMUM_ALIGNMENT_LAG_MINUTES: Final[int] = 15
    COMPONENT_WEIGHTS: Final[dict[str, int]] = {
        "BEARISH_DIRECTION": 50,
        "LIQUIDITY_SWEEP_COMPATIBLE_FAILED": 50,
    }
    _CSV_COLUMNS: Final[tuple[str, ...]] = (
        "Active Audit Timestamp",
        "Methodology Timestamp",
        "Alignment Method",
        "Alignment Lag Minutes",
        "Variant",
        "Score",
        "Research Cohort",
        "Bearish Direction Points",
        "Compatible Sweep Failed Points",
        "Bearish Direction Satisfied",
        "Compatible Sweep Failed",
        "Variant B Eligible",
        "Active Accepted",
        "Active Disposition",
        "Active Stage Reached",
        "Active Rejection Stage",
        "Active Reason Code",
        "Active Reason",
        "Outcome Complete",
        "Favorable Outcome",
        "Directional Return Percent",
        "Maximum Favorable Excursion",
        "Maximum Adverse Excursion",
        "Session",
        "Regime",
    )

    def __init__(
        self,
        output_directory: str | Path = "output/backtests",
    ) -> None:
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)

    def export(
        self,
        observations: Sequence[MethodologyObservation],
        audits: Sequence[PipelineObservationAudit],
        evaluations: Sequence[MethodologyOutcomeEvaluation],
        *,
        window_metadata: Mapping[str, object] | None = None,
    ) -> tuple[Path, Path]:
        payload, rows = self.calculate(
            observations,
            audits,
            evaluations,
            window_metadata=window_metadata,
        )
        csv_path = (
            self.output_directory
            / "methodology_variant_b_shadow_scoring.csv"
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
            / "methodology_variant_b_shadow_scoring.json"
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
        evaluations: Sequence[MethodologyOutcomeEvaluation],
        *,
        window_metadata: Mapping[str, object] | None = None,
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        observations_tuple = tuple(observations)
        audits_tuple = tuple(audits)
        evaluations_tuple = tuple(evaluations)
        metadata = dict(window_metadata or {})

        observation_index = {
            item.timestamp.astimezone(UTC): item
            for item in observations_tuple
        }
        observation_timestamps = tuple(sorted(observation_index))
        audit_index = {
            item.timestamp.astimezone(UTC): item
            for item in audits_tuple
        }
        outcome_index = {
            item.observation_timestamp.astimezone(UTC): item
            for item in evaluations_tuple
            if item.methodology is MethodologyIdentifier.SMC
            and item.direction is MethodologyDirection.BEARISH
            and item.horizon_bars == self.HORIZON_BARS
        }
        complete_outcome_timestamps = tuple(
            sorted(
                timestamp
                for timestamp, item in outcome_index.items()
                if item.horizon_complete
            )
        )

        common_window = self._common_window(
            tuple(sorted(audit_index)),
            observation_timestamps,
            complete_outcome_timestamps,
        )
        common_start = common_window[0] if common_window else None
        common_end = common_window[1] if common_window else None

        rows: list[dict[str, object]] = []
        unmatched = 0
        exact = 0
        asof = 0
        before = 0
        after = 0

        for audit_timestamp in sorted(audit_index):
            if common_start is None or common_end is None:
                continue
            if audit_timestamp < common_start:
                before += 1
                continue
            if audit_timestamp > common_end:
                after += 1
                continue

            matched = self._align(
                audit_timestamp,
                observation_timestamps,
            )
            if matched is None:
                unmatched += 1
                continue
            methodology_timestamp, method, lag_minutes = matched
            if lag_minutes > self.MAXIMUM_ALIGNMENT_LAG_MINUTES:
                unmatched += 1
                continue
            if method == "EXACT":
                exact += 1
            else:
                asof += 1

            observation = observation_index[methodology_timestamp]
            audit = audit_index[audit_timestamp]
            outcome = outcome_index.get(methodology_timestamp)

            bearish = (
                observation.smc.direction
                is MethodologyDirection.BEARISH
            )
            failed_codes = {
                item.code
                for item in observation.smc.failed_conditions
            }
            sweep_failed = (
                "LIQUIDITY_SWEEP_COMPATIBLE" in failed_codes
            )
            bearish_points = (
                self.COMPONENT_WEIGHTS["BEARISH_DIRECTION"]
                if bearish
                else 0
            )
            sweep_points = (
                self.COMPONENT_WEIGHTS[
                    "LIQUIDITY_SWEEP_COMPATIBLE_FAILED"
                ]
                if sweep_failed
                else 0
            )
            score = bearish_points + sweep_points
            research_cohort = self._research_cohort(
                bearish=bearish,
                sweep_failed=sweep_failed,
            )
            favorable = (
                outcome.favorable_terminal_outcome
                if outcome is not None and outcome.horizon_complete
                else None
            )
            rows.append(
                {
                    "Active Audit Timestamp": (
                        audit_timestamp.isoformat()
                    ),
                    "Methodology Timestamp": (
                        methodology_timestamp.isoformat()
                    ),
                    "Alignment Method": method,
                    "Alignment Lag Minutes": lag_minutes,
                    "Variant": self.VARIANT,
                    "Score": score,
                    "Research Cohort": research_cohort,
                    "Bearish Direction Points": bearish_points,
                    "Compatible Sweep Failed Points": sweep_points,
                    "Bearish Direction Satisfied": bearish,
                    "Compatible Sweep Failed": sweep_failed,
                    "Variant B Eligible": score == 100,
                    "Active Accepted": audit.accepted,
                    "Active Disposition": audit.disposition.value,
                    "Active Stage Reached": audit.stage_reached.value,
                    "Active Rejection Stage": (
                        audit.rejection_stage.value
                        if audit.rejection_stage is not None
                        else ""
                    ),
                    "Active Reason Code": audit.reason_code or "",
                    "Active Reason": audit.reason or "",
                    "Outcome Complete": (
                        outcome.horizon_complete
                        if outcome is not None
                        else False
                    ),
                    "Favorable Outcome": favorable,
                    "Directional Return Percent": (
                        outcome.directional_return_pct
                        if outcome is not None
                        and outcome.horizon_complete
                        else None
                    ),
                    "Maximum Favorable Excursion": (
                        outcome.maximum_favorable_excursion
                        if outcome is not None
                        and outcome.horizon_complete
                        else None
                    ),
                    "Maximum Adverse Excursion": (
                        outcome.maximum_adverse_excursion
                        if outcome is not None
                        and outcome.horizon_complete
                        else None
                    ),
                    "Session": observation.context.session_name,
                    "Regime": observation.context.regime_name,
                }
            )

        cohort_summaries = [
            self._summarize_cohort(cohort, rows)
            for cohort in (
                "SCORE_50_BASELINE",
                "SCORE_100_VARIANT_B",
            )
        ]
        out_of_scope_rows = [
            row
            for row in rows
            if row["Research Cohort"] == "OUT_OF_SCOPE_DIRECTION"
        ]
        inside = len(rows) + unmatched
        payload = {
            "variant": self.VARIANT,
            "horizon_bars": self.HORIZON_BARS,
            "component_weights": dict(self.COMPONENT_WEIGHTS),
            "cohorts": cohort_summaries,
            "out_of_scope_direction": {
                "classification": "OUT_OF_SCOPE_DIRECTION",
                "sample_count": len(out_of_scope_rows),
                "excluded_from_outcome_cohort_statistics": True,
                "active_accepted_count": sum(
                    bool(row["Active Accepted"])
                    for row in out_of_scope_rows
                ),
            },
            "window_metadata": metadata,
            "common_window": {
                "start": (
                    common_start.isoformat()
                    if common_start is not None
                    else None
                ),
                "end": (
                    common_end.isoformat()
                    if common_end is not None
                    else None
                ),
                "audit_count_before_window": before,
                "audit_count_inside_window": inside,
                "audit_count_after_window": after,
                "alignment_coverage_rate_inside_window": (
                    len(rows) / inside if inside else None
                ),
            },
            "alignment_policy": {
                "anchor": "ACTIVE_AUDIT_TIMESTAMP",
                "method": "EXACT_OR_ASOF_BACKWARD",
                "maximum_alignment_lag_minutes": (
                    self.MAXIMUM_ALIGNMENT_LAG_MINUTES
                ),
                "future_methodology_observations_allowed": False,
            },
            "aligned_audit_count": len(rows),
            "exact_alignment_count": exact,
            "asof_backward_alignment_count": asof,
            "unmatched_audit_count": unmatched,
            "observational_only": True,
            "trade_authority": False,
            "signal_authority": False,
            "approval_authority": False,
            "position_sizing_authority": False,
            "active_decision_modified": False,
            "active_pipeline_modified": False,
            "future_information_used_for_research_only": True,
        }
        return payload, rows

    @staticmethod
    def _research_cohort(
        *,
        bearish: bool,
        sweep_failed: bool,
    ) -> str:
        if not bearish:
            return "OUT_OF_SCOPE_DIRECTION"
        if sweep_failed:
            return "SCORE_100_VARIANT_B"
        return "SCORE_50_BASELINE"

    @staticmethod
    def _summarize_cohort(
        cohort: str,
        rows: Sequence[Mapping[str, object]],
    ) -> dict[str, object]:
        selected = [
            row
            for row in rows
            if row["Research Cohort"] == cohort
        ]
        if any(
            not bool(row["Bearish Direction Satisfied"])
            for row in selected
        ):
            raise RuntimeError(
                "direction-conditioned cohorts cannot contain "
                "non-bearish observations"
            )

        complete = [
            row
            for row in selected
            if row["Outcome Complete"]
            and row["Favorable Outcome"] is not None
        ]
        returns = [
            float(row["Directional Return Percent"])
            for row in complete
            if row["Directional Return Percent"] is not None
        ]
        rejection_reasons = Counter(
            str(row["Active Reason Code"])
            for row in selected
            if not row["Active Accepted"]
            and row["Active Reason Code"]
        )
        rejection_stages = Counter(
            str(row["Active Rejection Stage"])
            for row in selected
            if not row["Active Accepted"]
            and row["Active Rejection Stage"]
        )
        favorable_count = sum(
            row["Favorable Outcome"] is True for row in complete
        )
        expected_score = (
            100
            if cohort == "SCORE_100_VARIANT_B"
            else 50
        )
        return {
            "research_cohort": cohort,
            "score": expected_score,
            "direction": MethodologyDirection.BEARISH.value,
            "sample_count": len(selected),
            "complete_outcome_count": len(complete),
            "outcome_coverage_rate": (
                len(complete) / len(selected)
                if selected
                else None
            ),
            "favorable_count": favorable_count,
            "unfavorable_count": len(complete) - favorable_count,
            "favorable_rate": (
                favorable_count / len(complete)
                if complete
                else None
            ),
            "average_directional_return_percent": (
                sum(returns) / len(returns)
                if returns
                else None
            ),
            "active_accepted_count": sum(
                bool(row["Active Accepted"])
                for row in selected
            ),
            "active_rejection_stage_counts": dict(
                sorted(rejection_stages.items())
            ),
            "active_rejection_reason_counts": dict(
                sorted(rejection_reasons.items())
            ),
        }

    @staticmethod
    def _common_window(
        audit_timestamps: tuple[datetime, ...],
        observation_timestamps: tuple[datetime, ...],
        complete_outcome_timestamps: tuple[datetime, ...],
    ) -> tuple[datetime, datetime] | None:
        if (
            not audit_timestamps
            or not observation_timestamps
            or not complete_outcome_timestamps
        ):
            return None
        start = max(
            audit_timestamps[0],
            observation_timestamps[0],
            complete_outcome_timestamps[0],
        )
        end = min(
            audit_timestamps[-1],
            observation_timestamps[-1],
            complete_outcome_timestamps[-1],
        )
        return (start, end) if start <= end else None

    @staticmethod
    def _align(
        audit_timestamp: datetime,
        observation_timestamps: tuple[datetime, ...],
    ) -> tuple[datetime, str, float] | None:
        index = bisect_right(
            observation_timestamps,
            audit_timestamp,
        ) - 1
        if index < 0:
            return None
        methodology_timestamp = observation_timestamps[index]
        lag = audit_timestamp - methodology_timestamp
        if lag < timedelta(0):
            raise RuntimeError("alignment selected future observation")
        return (
            methodology_timestamp,
            (
                "EXACT"
                if methodology_timestamp == audit_timestamp
                else "ASOF_BACKWARD"
            ),
            lag.total_seconds() / 60.0,
        )
