"""Condition-level forward-outcome attribution for methodology research."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from core.strategies.methodology_models import (
    MethodologyDirection,
    MethodologyIdentifier,
    MethodologyResult,
)

from .methodology_observer import MethodologyObservation
from .methodology_outcome_research import MethodologyOutcomeEvaluation


class MethodologyConditionOutcomeAttribution:
    """Attribute forward outcomes to immutable methodology condition states."""

    DEFAULT_FOLD_COUNT: Final[int] = 5
    DEFAULT_MINIMUM_SAMPLE_SIZE: Final[int] = 30

    _CSV_COLUMNS: Final[tuple[str, ...]] = (
        "Methodology",
        "Condition Code",
        "Required",
        "Direction",
        "Horizon Bars",
        "Satisfied Sample Count",
        "Failed Sample Count",
        "Unavailable Sample Count",
        "Satisfied Favorable Rate",
        "Failed Favorable Rate",
        "Favorable Rate Delta",
        "Satisfied Average Return Percent",
        "Failed Average Return Percent",
        "Average Return Delta Percent",
        "Satisfied MFE MAE Ratio",
        "Failed MFE MAE Ratio",
        "Valid Fold Count",
        "Positive Favorable Delta Folds",
        "Positive Return Delta Folds",
        "Sample Warning",
        "Stability Warnings",
    )

    def __init__(
        self,
        output_directory: str | Path = "output/backtests",
        *,
        fold_count: int = DEFAULT_FOLD_COUNT,
        minimum_sample_size: int = DEFAULT_MINIMUM_SAMPLE_SIZE,
    ) -> None:
        if isinstance(fold_count, bool) or not isinstance(fold_count, int):
            raise TypeError("fold_count must be an integer")
        if fold_count < 2:
            raise ValueError("fold_count must be at least two")
        if isinstance(minimum_sample_size, bool) or not isinstance(
            minimum_sample_size,
            int,
        ):
            raise TypeError("minimum_sample_size must be an integer")
        if minimum_sample_size < 1:
            raise ValueError("minimum_sample_size must be positive")

        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.fold_count = fold_count
        self.minimum_sample_size = minimum_sample_size

    def export(
        self,
        observations: Sequence[MethodologyObservation],
        evaluations: Sequence[MethodologyOutcomeEvaluation],
        *,
        window_metadata: Mapping[str, object] | None = None,
    ) -> tuple[Path, Path]:
        """Write aggregate condition attribution and fold stability artifacts."""

        payload, rows = self.calculate(
            observations,
            evaluations,
            window_metadata=window_metadata,
        )

        csv_path = (
            self.output_directory
            / "methodology_condition_outcome_attribution.csv"
        )
        with csv_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=list(self._CSV_COLUMNS),
                extrasaction="raise",
            )
            writer.writeheader()
            writer.writerows(
                {
                    column: row.get(column, "")
                    for column in self._CSV_COLUMNS
                }
                for row in rows
            )

        json_path = (
            self.output_directory
            / "methodology_condition_outcome_attribution.json"
        )
        json_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return csv_path, json_path

    def calculate(
        self,
        observations: Sequence[MethodologyObservation],
        evaluations: Sequence[MethodologyOutcomeEvaluation],
        *,
        window_metadata: Mapping[str, object] | None = None,
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        """Join immutable observations to outcomes and calculate attribution."""

        validated_observations = self._validate_observations(observations)
        validated_evaluations = self._validate_evaluations(evaluations)
        metadata = self._validate_window_metadata(window_metadata)

        result_index: dict[
            tuple[datetime, MethodologyIdentifier],
            MethodologyResult,
        ] = {}
        condition_catalog: dict[
            tuple[MethodologyIdentifier, str],
            dict[str, object],
        ] = {}
        for observation in validated_observations:
            for result in (observation.smc, observation.ict):
                key = (
                    observation.timestamp.astimezone(UTC),
                    result.methodology,
                )
                result_index[key] = result
                for state, conditions in self._condition_sets(result).items():
                    for condition in conditions:
                        condition_catalog[
                            (result.methodology, condition.code)
                        ] = {
                            "methodology": result.methodology.value,
                            "condition_code": condition.code,
                            "description": condition.description,
                            "required": condition.required,
                            "source_capability": condition.source_capability,
                            "evidence_reference": condition.evidence_reference,
                        }

        usable = tuple(
            item
            for item in validated_evaluations
            if item.horizon_complete
            and item.direction
            in {
                MethodologyDirection.BULLISH,
                MethodologyDirection.BEARISH,
            }
        )

        missing_join_keys = sorted(
            {
                (
                    item.observation_timestamp.astimezone(UTC),
                    item.methodology,
                )
                for item in usable
                if (
                    item.observation_timestamp.astimezone(UTC),
                    item.methodology,
                )
                not in result_index
            },
            key=lambda value: (value[0], value[1].value),
        )
        if missing_join_keys:
            raise ValueError(
                "outcome evaluations contain observation/methodology keys "
                "without matching methodology results"
            )

        timestamps = tuple(
            sorted({item.observation_timestamp.astimezone(UTC) for item in usable})
        )
        folds = self._build_folds(timestamps)

        aggregate_rows = self._comparison_rows(
            usable,
            result_index,
            condition_catalog,
        )
        fold_rows: list[dict[str, object]] = []
        for fold_number, fold_timestamps in enumerate(folds, start=1):
            allowed = set(fold_timestamps)
            fold_evaluations = tuple(
                item
                for item in usable
                if item.observation_timestamp.astimezone(UTC) in allowed
            )
            for row in self._comparison_rows(
                fold_evaluations,
                result_index,
                condition_catalog,
            ):
                fold_rows.append(
                    {
                        "fold_number": fold_number,
                        "start_timestamp": (
                            fold_timestamps[0].isoformat()
                            if fold_timestamps
                            else None
                        ),
                        "end_timestamp": (
                            fold_timestamps[-1].isoformat()
                            if fold_timestamps
                            else None
                        ),
                        "observation_count": len(fold_timestamps),
                        **row,
                    }
                )

        stability = self._stability_summary(fold_rows)
        stability_index = {
            (
                item["Methodology"],
                item["Condition Code"],
                item["Direction"],
                item["Horizon Bars"],
            ): item
            for item in stability
        }

        csv_rows: list[dict[str, object]] = []
        for row in aggregate_rows:
            summary = stability_index.get(
                (
                    row["Methodology"],
                    row["Condition Code"],
                    row["Direction"],
                    row["Horizon Bars"],
                ),
                {},
            )
            csv_rows.append(
                {
                    **row,
                    "Valid Fold Count": summary.get("Valid Fold Count", 0),
                    "Positive Favorable Delta Folds": summary.get(
                        "Positive Favorable Delta Folds",
                        0,
                    ),
                    "Positive Return Delta Folds": summary.get(
                        "Positive Return Delta Folds",
                        0,
                    ),
                    "Stability Warnings": "|".join(
                        summary.get("Stability Warnings", [])
                    ),
                }
            )

        payload: dict[str, object] = {
            "window_metadata": metadata,
            "fold_count": self.fold_count,
            "minimum_sample_size": self.minimum_sample_size,
            "observation_count": len(validated_observations),
            "evaluation_count": len(validated_evaluations),
            "usable_directional_complete_evaluation_count": len(usable),
            "condition_catalog": [
                condition_catalog[key]
                for key in sorted(
                    condition_catalog,
                    key=lambda item: (item[0].value, item[1]),
                )
            ],
            "aggregate_comparisons": aggregate_rows,
            "fold_comparisons": fold_rows,
            "stability_summary": stability,
            "observational_only": True,
            "trade_authority": False,
            "future_information_used_for_research_only": True,
        }
        return payload, csv_rows

    def _comparison_rows(
        self,
        evaluations: tuple[MethodologyOutcomeEvaluation, ...],
        result_index: Mapping[
            tuple[datetime, MethodologyIdentifier],
            MethodologyResult,
        ],
        condition_catalog: Mapping[
            tuple[MethodologyIdentifier, str],
            Mapping[str, object],
        ],
    ) -> list[dict[str, object]]:
        grouped: dict[
            tuple[
                MethodologyIdentifier,
                str,
                MethodologyDirection,
                int,
                str,
            ],
            list[MethodologyOutcomeEvaluation],
        ] = {}

        for item in evaluations:
            result = result_index[
                (
                    item.observation_timestamp.astimezone(UTC),
                    item.methodology,
                )
            ]
            states = {
                condition.code: state
                for state, conditions in self._condition_sets(result).items()
                for condition in conditions
            }
            for condition_code, state in states.items():
                grouped.setdefault(
                    (
                        item.methodology,
                        condition_code,
                        item.direction,
                        item.horizon_bars,
                        state,
                    ),
                    [],
                ).append(item)

        base_keys = sorted(
            {
                (methodology, code, direction, horizon)
                for methodology, code, direction, horizon, _ in grouped
            },
            key=lambda item: (
                item[0].value,
                item[1],
                item[2].value,
                item[3],
            ),
        )
        rows: list[dict[str, object]] = []
        for methodology, code, direction, horizon in base_keys:
            satisfied = grouped.get(
                (methodology, code, direction, horizon, "SATISFIED"),
                [],
            )
            failed = grouped.get(
                (methodology, code, direction, horizon, "FAILED"),
                [],
            )
            unavailable = grouped.get(
                (methodology, code, direction, horizon, "UNAVAILABLE"),
                [],
            )
            sat = self._statistics(satisfied)
            fail = self._statistics(failed)
            catalog = condition_catalog[(methodology, code)]
            warning = self._sample_warning(
                len(satisfied),
                len(failed),
            )
            rows.append(
                {
                    "Methodology": methodology.value,
                    "Condition Code": code,
                    "Required": catalog["required"],
                    "Direction": direction.value,
                    "Horizon Bars": horizon,
                    "Satisfied Sample Count": len(satisfied),
                    "Failed Sample Count": len(failed),
                    "Unavailable Sample Count": len(unavailable),
                    "Satisfied Favorable Rate": sat["favorable_rate"],
                    "Failed Favorable Rate": fail["favorable_rate"],
                    "Favorable Rate Delta": self._difference(
                        sat["favorable_rate"],
                        fail["favorable_rate"],
                    ),
                    "Satisfied Average Return Percent": sat[
                        "average_return_percent"
                    ],
                    "Failed Average Return Percent": fail[
                        "average_return_percent"
                    ],
                    "Average Return Delta Percent": self._difference(
                        sat["average_return_percent"],
                        fail["average_return_percent"],
                    ),
                    "Satisfied Average MFE": sat["average_mfe"],
                    "Failed Average MFE": fail["average_mfe"],
                    "Satisfied Average MAE": sat["average_mae"],
                    "Failed Average MAE": fail["average_mae"],
                    "Satisfied MFE MAE Ratio": sat["mfe_mae_ratio"],
                    "Failed MFE MAE Ratio": fail["mfe_mae_ratio"],
                    "Sample Warning": warning,
                }
            )
        return rows

    def _stability_summary(
        self,
        fold_rows: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        grouped: dict[
            tuple[str, str, str, int],
            list[dict[str, object]],
        ] = {}
        for row in fold_rows:
            key = (
                str(row["Methodology"]),
                str(row["Condition Code"]),
                str(row["Direction"]),
                int(row["Horizon Bars"]),
            )
            grouped.setdefault(key, []).append(row)

        summaries: list[dict[str, object]] = []
        for key in sorted(grouped):
            rows = grouped[key]
            valid = [
                row
                for row in rows
                if not row["Sample Warning"]
                and row["Favorable Rate Delta"] is not None
                and row["Average Return Delta Percent"] is not None
            ]
            favorable_positive = sum(
                float(row["Favorable Rate Delta"]) > 0.0
                for row in valid
            )
            return_positive = sum(
                float(row["Average Return Delta Percent"]) > 0.0
                for row in valid
            )
            warnings: list[str] = []
            if len(valid) < self.fold_count:
                warnings.append("INSUFFICIENT_VALID_FOLDS")
            if not valid:
                warnings.append("NO_VALID_FOLDS")
            else:
                if favorable_positive not in {0, len(valid)}:
                    warnings.append("FAVORABLE_RATE_SIGN_UNSTABLE")
                if return_positive not in {0, len(valid)}:
                    warnings.append("RETURN_SIGN_UNSTABLE")

            summaries.append(
                {
                    "Methodology": key[0],
                    "Condition Code": key[1],
                    "Direction": key[2],
                    "Horizon Bars": key[3],
                    "Valid Fold Count": len(valid),
                    "Positive Favorable Delta Folds": favorable_positive,
                    "Positive Return Delta Folds": return_positive,
                    "Average Favorable Rate Delta": self._average_field(
                        valid,
                        "Favorable Rate Delta",
                    ),
                    "Average Return Delta Percent": self._average_field(
                        valid,
                        "Average Return Delta Percent",
                    ),
                    "Stability Warnings": warnings,
                }
            )
        return summaries

    @staticmethod
    def _condition_sets(
        result: MethodologyResult,
    ) -> dict[str, tuple[object, ...]]:
        return {
            "SATISFIED": result.satisfied_conditions,
            "FAILED": result.failed_conditions,
            "UNAVAILABLE": result.unavailable_conditions,
        }

    @staticmethod
    def _statistics(
        evaluations: Sequence[MethodologyOutcomeEvaluation],
    ) -> dict[str, float | None]:
        if not evaluations:
            return {
                "favorable_rate": None,
                "average_return_percent": None,
                "average_mfe": None,
                "average_mae": None,
                "mfe_mae_ratio": None,
            }
        count = len(evaluations)
        favorable_rate = sum(
            item.favorable_terminal_outcome is True
            for item in evaluations
        ) / count
        average_return = sum(
            float(item.directional_return_pct)
            for item in evaluations
        ) / count
        average_mfe = sum(
            float(item.maximum_favorable_excursion)
            for item in evaluations
        ) / count
        average_mae = sum(
            float(item.maximum_adverse_excursion)
            for item in evaluations
        ) / count
        return {
            "favorable_rate": favorable_rate,
            "average_return_percent": average_return,
            "average_mfe": average_mfe,
            "average_mae": average_mae,
            "mfe_mae_ratio": (
                average_mfe / average_mae
                if average_mae > 0.0
                else None
            ),
        }

    def _sample_warning(
        self,
        satisfied_count: int,
        failed_count: int,
    ) -> str:
        warnings: list[str] = []
        if satisfied_count == 0:
            warnings.append("NO_SATISFIED_SAMPLE")
        elif satisfied_count < self.minimum_sample_size:
            warnings.append("INSUFFICIENT_SATISFIED_SAMPLE")
        if failed_count == 0:
            warnings.append("NO_FAILED_SAMPLE")
        elif failed_count < self.minimum_sample_size:
            warnings.append("INSUFFICIENT_FAILED_SAMPLE")
        return "|".join(warnings)

    def _build_folds(
        self,
        timestamps: tuple[datetime, ...],
    ) -> tuple[tuple[datetime, ...], ...]:
        folds: list[list[datetime]] = [
            [] for _ in range(self.fold_count)
        ]
        if not timestamps:
            return tuple(tuple(fold) for fold in folds)
        total = len(timestamps)
        for index, timestamp in enumerate(timestamps):
            fold_index = min(
                (index * self.fold_count) // total,
                self.fold_count - 1,
            )
            folds[fold_index].append(timestamp)
        return tuple(tuple(fold) for fold in folds)

    @staticmethod
    def _difference(
        left: float | None,
        right: float | None,
    ) -> float | None:
        if left is None or right is None:
            return None
        return left - right

    @staticmethod
    def _average_field(
        rows: Sequence[Mapping[str, object]],
        field: str,
    ) -> float | None:
        if not rows:
            return None
        return sum(float(row[field]) for row in rows) / len(rows)

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
                "observations must contain MethodologyObservation"
            )
        timestamps = tuple(item.timestamp for item in validated)
        if timestamps != tuple(sorted(timestamps)):
            raise ValueError("observations must be chronologically ordered")
        if len(timestamps) != len(set(timestamps)):
            raise ValueError("observation timestamps must be unique")
        return validated

    @staticmethod
    def _validate_evaluations(
        evaluations: Sequence[MethodologyOutcomeEvaluation],
    ) -> tuple[MethodologyOutcomeEvaluation, ...]:
        if isinstance(evaluations, (str, bytes)) or not isinstance(
            evaluations,
            Sequence,
        ):
            raise TypeError(
                "evaluations must be a sequence of "
                "MethodologyOutcomeEvaluation"
            )
        validated = tuple(evaluations)
        if any(
            not isinstance(item, MethodologyOutcomeEvaluation)
            for item in validated
        ):
            raise TypeError(
                "evaluations must contain MethodologyOutcomeEvaluation"
            )
        return validated

    @staticmethod
    def _validate_window_metadata(
        metadata: Mapping[str, object] | None,
    ) -> dict[str, object]:
        if metadata is None:
            return {}
        if not isinstance(metadata, Mapping):
            raise TypeError("window_metadata must be a mapping or None")
        return dict(metadata)
