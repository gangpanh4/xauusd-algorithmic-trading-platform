"""Condition-level analytics for observational SMC and ICT results."""

from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from core.strategies.methodology_models import (
    MethodologyCondition,
    MethodologyEvaluationStatus,
    MethodologyIdentifier,
    MethodologyResult,
)

from .methodology_observer import MethodologyObservation


class MethodologyConditionAnalytics:
    """Aggregate immutable methodology observations for research diagnostics."""

    _CONDITION_COLUMNS: Final[tuple[str, ...]] = (
        "Methodology",
        "Condition Code",
        "Description",
        "Required",
        "Source Capability",
        "Evidence Reference",
        "Total Evaluations",
        "Satisfied Count",
        "Failed Count",
        "Unavailable Count",
        "Satisfied Rate",
        "Failed Rate",
        "Unavailable Rate",
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
    ) -> tuple[Path, Path]:
        """Write condition CSV and multidimensional JSON analytics."""

        validated = self._validate_observations(observations)
        payload, condition_rows = self.calculate(validated)

        csv_path = self.output_directory / "methodology_condition_summary.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=list(self._CONDITION_COLUMNS),
                extrasaction="raise",
            )
            writer.writeheader()
            writer.writerows(condition_rows)

        json_path = self.output_directory / "methodology_condition_summary.json"
        json_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return csv_path, json_path

    @classmethod
    def calculate(
        cls,
        observations: Sequence[MethodologyObservation],
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        """Return deterministic aggregate payload and condition table rows."""

        validated = cls._validate_observations(observations)
        condition_stats: dict[
            tuple[str, str],
            dict[str, object],
        ] = {}
        status_counts: dict[str, int] = {}
        direction_counts: dict[str, dict[str, int]] = {
            "SMC": {},
            "ICT": {},
        }
        by_session: dict[str, dict[str, object]] = {}
        by_regime: dict[str, dict[str, object]] = {}
        overlap: dict[str, int] = {}

        for observation in validated:
            results = (observation.smc, observation.ict)
            for result in results:
                methodology = result.methodology.value
                status = result.evaluation_status.value
                status_key = f"{methodology}:{status}"
                status_counts[status_key] = status_counts.get(status_key, 0) + 1

                direction = result.direction.value
                direction_bucket = direction_counts[methodology]
                direction_bucket[direction] = (
                    direction_bucket.get(direction, 0) + 1
                )

                cls._accumulate_dimension(
                    by_session,
                    observation.context.session_name or "OFF_SESSION",
                    result,
                )
                cls._accumulate_dimension(
                    by_regime,
                    observation.context.regime_name or "MISSING",
                    result,
                )
                cls._accumulate_conditions(condition_stats, result)

            overlap_key = (
                f"SMC_{observation.smc.evaluation_status.value}__"
                f"ICT_{observation.ict.evaluation_status.value}"
            )
            overlap[overlap_key] = overlap.get(overlap_key, 0) + 1

        condition_rows = cls._condition_rows(condition_stats)
        payload: dict[str, object] = {
            "total_observations": len(validated),
            "status_counts": dict(sorted(status_counts.items())),
            "condition_counts": {
                methodology: {
                    row["Condition Code"]: {
                        "required": row["Required"],
                        "description": row["Description"],
                        "source_capability": row["Source Capability"] or None,
                        "evidence_reference": row["Evidence Reference"] or None,
                        "total_evaluations": row["Total Evaluations"],
                        "satisfied": row["Satisfied Count"],
                        "failed": row["Failed Count"],
                        "unavailable": row["Unavailable Count"],
                        "satisfied_rate": row["Satisfied Rate"],
                        "failed_rate": row["Failed Rate"],
                        "unavailable_rate": row["Unavailable Rate"],
                    }
                    for row in condition_rows
                    if row["Methodology"] == methodology
                }
                for methodology in ("SMC", "ICT")
            },
            "confirmation_by_session": cls._finalize_dimension(by_session),
            "confirmation_by_regime": cls._finalize_dimension(by_regime),
            "direction_counts": {
                key: dict(sorted(value.items()))
                for key, value in direction_counts.items()
            },
            "status_overlap": dict(sorted(overlap.items())),
            "observational_only": True,
            "trade_authority": False,
        }
        return payload, condition_rows

    @staticmethod
    def _accumulate_dimension(
        target: dict[str, dict[str, object]],
        dimension_value: str,
        result: MethodologyResult,
    ) -> None:
        bucket = target.setdefault(
            dimension_value,
            {
                "total_observations": 0,
                "SMC": {},
                "ICT": {},
            },
        )
        methodology = result.methodology.value
        status = result.evaluation_status.value
        methodology_counts = bucket[methodology]
        if not isinstance(methodology_counts, dict):
            raise TypeError("dimension methodology bucket must be a dictionary")
        methodology_counts[status] = methodology_counts.get(status, 0) + 1

        # Each observation contributes SMC first and ICT second. Increment the
        # dimension total only for SMC so it remains one count per candle.
        if result.methodology is MethodologyIdentifier.SMC:
            bucket["total_observations"] = int(bucket["total_observations"]) + 1

    @staticmethod
    def _finalize_dimension(
        values: dict[str, dict[str, object]],
    ) -> dict[str, dict[str, object]]:
        finalized: dict[str, dict[str, object]] = {}
        for dimension_value in sorted(values):
            raw = values[dimension_value]
            total = int(raw["total_observations"])
            entry: dict[str, object] = {"total_observations": total}
            for methodology in ("SMC", "ICT"):
                counts = raw[methodology]
                if not isinstance(counts, dict):
                    raise TypeError(
                        "dimension methodology counts must be a dictionary"
                    )
                confirmed = int(
                    counts.get(MethodologyEvaluationStatus.CONFIRMED.value, 0)
                )
                not_confirmed = int(
                    counts.get(
                        MethodologyEvaluationStatus.NOT_CONFIRMED.value,
                        0,
                    )
                )
                incomplete = int(
                    counts.get(MethodologyEvaluationStatus.INCOMPLETE.value, 0)
                )
                entry[methodology] = {
                    "CONFIRMED": confirmed,
                    "NOT_CONFIRMED": not_confirmed,
                    "INCOMPLETE": incomplete,
                    "confirmation_rate": (
                        confirmed / total if total else 0.0
                    ),
                }
            finalized[dimension_value] = entry
        return finalized

    @staticmethod
    def _accumulate_conditions(
        target: dict[tuple[str, str], dict[str, object]],
        result: MethodologyResult,
    ) -> None:
        grouped = (
            ("satisfied", result.satisfied_conditions),
            ("failed", result.failed_conditions),
            ("unavailable", result.unavailable_conditions),
        )
        for state, conditions in grouped:
            for condition in conditions:
                key = (result.methodology.value, condition.code)
                bucket = target.setdefault(
                    key,
                    MethodologyConditionAnalytics._new_condition_bucket(
                        result.methodology,
                        condition,
                    ),
                )
                bucket[state] = int(bucket[state]) + 1

    @staticmethod
    def _new_condition_bucket(
        methodology: MethodologyIdentifier,
        condition: MethodologyCondition,
    ) -> dict[str, object]:
        return {
            "methodology": methodology.value,
            "condition_code": condition.code,
            "description": condition.description,
            "required": condition.required,
            "source_capability": condition.source_capability,
            "evidence_reference": condition.evidence_reference,
            "satisfied": 0,
            "failed": 0,
            "unavailable": 0,
        }

    @staticmethod
    def _condition_rows(
        stats: dict[tuple[str, str], dict[str, object]],
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for key in sorted(stats):
            bucket = stats[key]
            satisfied = int(bucket["satisfied"])
            failed = int(bucket["failed"])
            unavailable = int(bucket["unavailable"])
            total = satisfied + failed + unavailable
            rows.append(
                {
                    "Methodology": bucket["methodology"],
                    "Condition Code": bucket["condition_code"],
                    "Description": bucket["description"],
                    "Required": bucket["required"],
                    "Source Capability": bucket["source_capability"] or "",
                    "Evidence Reference": bucket["evidence_reference"] or "",
                    "Total Evaluations": total,
                    "Satisfied Count": satisfied,
                    "Failed Count": failed,
                    "Unavailable Count": unavailable,
                    "Satisfied Rate": satisfied / total if total else 0.0,
                    "Failed Rate": failed / total if total else 0.0,
                    "Unavailable Rate": unavailable / total if total else 0.0,
                }
            )
        return rows

    @staticmethod
    def _validate_observations(
        observations: Sequence[MethodologyObservation],
    ) -> tuple[MethodologyObservation, ...]:
        if isinstance(observations, (str, bytes)) or not isinstance(
            observations,
            Sequence,
        ):
            raise TypeError(
                "observations must be a sequence of MethodologyObservation"
            )
        validated = tuple(observations)
        if any(
            not isinstance(item, MethodologyObservation)
            for item in validated
        ):
            raise TypeError(
                "observations must contain MethodologyObservation instances"
            )
        timestamps = tuple(item.timestamp for item in validated)
        if timestamps != tuple(sorted(timestamps)):
            raise ValueError(
                "methodology observations must be chronologically ordered"
            )
        if len(timestamps) != len(set(timestamps)):
            raise ValueError(
                "methodology observation timestamps must be unique"
            )
        return validated
