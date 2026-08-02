"""Shadow-only comparison of methodology candidates and active decisions."""

from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from core.strategies.methodology_models import (
    MethodologyDirection,
    MethodologyIdentifier,
    MethodologyResult,
)
from core.trading_pipeline.models import PipelineObservationAudit

from .methodology_observer import MethodologyObservation
from .methodology_outcome_research import MethodologyOutcomeEvaluation


class MethodologyShadowDecisionComparison:
    """Compare frozen shadow eligibility with immutable active decisions."""

    HORIZON_BARS: Final[int] = 24
    VARIANTS: Final[tuple[dict[str, object], ...]] = (
        {
            "variant": "VARIANT_A_BULLISH_ORDER_BLOCK_STRUCTURE",
            "direction": MethodologyDirection.BULLISH,
            "required_satisfied": (
                "ORDER_BLOCK_PRESENT",
                "STRUCTURE_EVENT_ALIGNED",
            ),
            "required_failed": (),
        },
        {
            "variant": "VARIANT_B_BEARISH_EXCLUDE_COMPATIBLE_SWEEP",
            "direction": MethodologyDirection.BEARISH,
            "required_satisfied": (),
            "required_failed": ("LIQUIDITY_SWEEP_COMPATIBLE",),
        },
    )

    _CSV_COLUMNS: Final[tuple[str, ...]] = (
        "Timestamp",
        "Variant",
        "Direction",
        "Active Accepted",
        "Active Disposition",
        "Active Stage Reached",
        "Active Rejection Stage",
        "Active Reason Code",
        "Active Reason",
        "Shadow Eligible",
        "Agreement",
        "Research Classification",
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
            / "methodology_shadow_decision_comparison.csv"
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
            / "methodology_shadow_decision_comparison.json"
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
        observations_tuple = self._validate_observations(observations)
        audits_tuple = self._validate_audits(audits)
        evaluations_tuple = self._validate_evaluations(evaluations)
        metadata = self._validate_metadata(window_metadata)

        observation_index = {
            item.timestamp.astimezone(UTC): item
            for item in observations_tuple
        }
        audit_index = {
            item.timestamp.astimezone(UTC): item
            for item in audits_tuple
        }
        outcome_index = {
            (
                item.observation_timestamp.astimezone(UTC),
                item.direction,
            ): item
            for item in evaluations_tuple
            if item.methodology is MethodologyIdentifier.SMC
            and item.horizon_bars == self.HORIZON_BARS
        }

        shared_timestamps = tuple(
            sorted(set(observation_index).intersection(audit_index))
        )
        unmatched_observations = tuple(
            sorted(set(observation_index).difference(audit_index))
        )
        unmatched_audits = tuple(
            sorted(set(audit_index).difference(observation_index))
        )

        rows: list[dict[str, object]] = []
        summaries: list[dict[str, object]] = []

        for variant in self.VARIANTS:
            direction = variant["direction"]
            variant_rows: list[dict[str, object]] = []
            for timestamp in shared_timestamps:
                observation = observation_index[timestamp]
                if observation.smc.direction is not direction:
                    continue

                audit = audit_index[timestamp]
                outcome = outcome_index.get((timestamp, direction))
                eligible = self._matches_variant(variant, observation.smc)
                active_accepted = audit.accepted
                favorable = (
                    outcome.favorable_terminal_outcome
                    if outcome is not None and outcome.horizon_complete
                    else None
                )
                agreement = (
                    "AGREE_ACCEPT"
                    if active_accepted and eligible
                    else "AGREE_REJECT"
                    if not active_accepted and not eligible
                    else "SHADOW_ONLY"
                    if eligible
                    else "ACTIVE_ONLY"
                )
                classification = self._research_classification(
                    eligible=eligible,
                    favorable=favorable,
                )
                row = {
                    "Timestamp": timestamp.isoformat(),
                    "Variant": variant["variant"],
                    "Direction": direction.value,
                    "Active Accepted": active_accepted,
                    "Active Disposition": audit.disposition.value,
                    "Active Stage Reached": audit.stage_reached.value,
                    "Active Rejection Stage": (
                        audit.rejection_stage.value
                        if audit.rejection_stage is not None
                        else ""
                    ),
                    "Active Reason Code": audit.reason_code or "",
                    "Active Reason": audit.reason or "",
                    "Shadow Eligible": eligible,
                    "Agreement": agreement,
                    "Research Classification": classification,
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
                variant_rows.append(row)
                rows.append(row)

            summaries.append(
                self._summarize_variant(variant, variant_rows)
            )

        payload: dict[str, object] = {
            "window_metadata": metadata,
            "horizon_bars": self.HORIZON_BARS,
            "observation_count": len(observations_tuple),
            "audit_count": len(audits_tuple),
            "evaluation_count": len(evaluations_tuple),
            "shared_timestamp_count": len(shared_timestamps),
            "unmatched_observation_timestamps": [
                item.isoformat() for item in unmatched_observations
            ],
            "unmatched_audit_timestamps": [
                item.isoformat() for item in unmatched_audits
            ],
            "variants": summaries,
            "observational_only": True,
            "trade_authority": False,
            "active_decision_modified": False,
            "active_pipeline_modified": False,
            "future_information_used_for_research_only": True,
        }
        return payload, rows

    def _summarize_variant(
        self,
        variant: Mapping[str, object],
        rows: Sequence[Mapping[str, object]],
    ) -> dict[str, object]:
        agreement = Counter(str(row["Agreement"]) for row in rows)
        classifications = Counter(
            str(row["Research Classification"]) for row in rows
        )
        rejection_reasons = Counter(
            str(row["Active Reason Code"])
            for row in rows
            if row["Shadow Eligible"]
            and not row["Active Accepted"]
            and row["Active Reason Code"]
        )
        sessions = Counter(
            str(row["Session"] or "OFF_SESSION")
            for row in rows
            if row["Shadow Eligible"]
        )
        regimes = Counter(
            str(row["Regime"] or "MISSING")
            for row in rows
            if row["Shadow Eligible"]
        )
        eligible_rows = [row for row in rows if row["Shadow Eligible"]]
        complete_eligible = [
            row
            for row in eligible_rows
            if row["Outcome Complete"]
            and row["Favorable Outcome"] is not None
        ]
        active_rows = [row for row in rows if row["Active Accepted"]]
        return {
            "variant": variant["variant"],
            "direction": variant["direction"].value,
            "direction_observation_count": len(rows),
            "shadow_eligible_count": len(eligible_rows),
            "active_accepted_count": len(active_rows),
            "shadow_retention_rate": (
                len(eligible_rows) / len(rows) if rows else None
            ),
            "agreement_counts": dict(sorted(agreement.items())),
            "research_classification_counts": dict(
                sorted(classifications.items())
            ),
            "shadow_false_positive_count": classifications.get(
                "SHADOW_FALSE_POSITIVE",
                0,
            ),
            "shadow_false_negative_count": classifications.get(
                "SHADOW_FALSE_NEGATIVE",
                0,
            ),
            "complete_shadow_outcome_count": len(complete_eligible),
            "shadow_favorable_rate": (
                sum(row["Favorable Outcome"] is True for row in complete_eligible)
                / len(complete_eligible)
                if complete_eligible
                else None
            ),
            "shadow_average_return_percent": (
                sum(
                    float(row["Directional Return Percent"])
                    for row in complete_eligible
                )
                / len(complete_eligible)
                if complete_eligible
                else None
            ),
            "shadow_only_rejection_reason_counts": dict(
                sorted(rejection_reasons.items())
            ),
            "shadow_session_counts": dict(sorted(sessions.items())),
            "shadow_regime_counts": dict(sorted(regimes.items())),
        }

    @staticmethod
    def _research_classification(
        *,
        eligible: bool,
        favorable: bool | None,
    ) -> str:
        if favorable is None:
            return "OUTCOME_UNAVAILABLE"
        if eligible and favorable:
            return "SHADOW_TRUE_POSITIVE"
        if eligible and not favorable:
            return "SHADOW_FALSE_POSITIVE"
        if not eligible and favorable:
            return "SHADOW_FALSE_NEGATIVE"
        return "SHADOW_TRUE_NEGATIVE"

    @staticmethod
    def _matches_variant(
        variant: Mapping[str, object],
        result: MethodologyResult,
    ) -> bool:
        satisfied = {
            condition.code for condition in result.satisfied_conditions
        }
        failed = {
            condition.code for condition in result.failed_conditions
        }
        return all(
            code in satisfied for code in variant["required_satisfied"]
        ) and all(
            code in failed for code in variant["required_failed"]
        )

    @staticmethod
    def _validate_observations(
        observations: Sequence[MethodologyObservation],
    ) -> tuple[MethodologyObservation, ...]:
        if isinstance(observations, (str, bytes)) or not isinstance(
            observations,
            Sequence,
        ):
            raise TypeError("observations must be a sequence")
        values = tuple(observations)
        if any(not isinstance(item, MethodologyObservation) for item in values):
            raise TypeError(
                "observations must contain MethodologyObservation"
            )
        return values

    @staticmethod
    def _validate_audits(
        audits: Sequence[PipelineObservationAudit],
    ) -> tuple[PipelineObservationAudit, ...]:
        if isinstance(audits, (str, bytes)) or not isinstance(
            audits,
            Sequence,
        ):
            raise TypeError("audits must be a sequence")
        values = tuple(audits)
        if any(not isinstance(item, PipelineObservationAudit) for item in values):
            raise TypeError(
                "audits must contain PipelineObservationAudit"
            )
        return values

    @staticmethod
    def _validate_evaluations(
        evaluations: Sequence[MethodologyOutcomeEvaluation],
    ) -> tuple[MethodologyOutcomeEvaluation, ...]:
        if isinstance(evaluations, (str, bytes)) or not isinstance(
            evaluations,
            Sequence,
        ):
            raise TypeError("evaluations must be a sequence")
        values = tuple(evaluations)
        if any(
            not isinstance(item, MethodologyOutcomeEvaluation)
            for item in values
        ):
            raise TypeError(
                "evaluations must contain MethodologyOutcomeEvaluation"
            )
        return values

    @staticmethod
    def _validate_metadata(
        metadata: Mapping[str, object] | None,
    ) -> dict[str, object]:
        if metadata is None:
            return {}
        if not isinstance(metadata, Mapping):
            raise TypeError("window_metadata must be a mapping or None")
        return dict(metadata)
