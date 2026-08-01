"""Frozen counterfactual cohort research for methodology observations."""

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

from .methodology_observer import MethodologyObservation
from .methodology_outcome_research import MethodologyOutcomeEvaluation


class MethodologyCounterfactualCohorts:
    """Evaluate predeclared SMC cohorts without changing methodology authority."""

    DEFAULT_FOLD_COUNT: Final[int] = 5
    DEFAULT_MINIMUM_SAMPLE_SIZE: Final[int] = 30
    HORIZONS: Final[tuple[int, ...]] = (12, 24)

    CANDIDATES: Final[tuple[dict[str, object], ...]] = (
        {
            "candidate": "BULLISH_ORDER_BLOCK_PRESENT",
            "direction": MethodologyDirection.BULLISH,
            "condition": "ORDER_BLOCK_PRESENT",
            "positive_label": "PRESENT",
            "negative_label": "ABSENT",
            "controls": (
                "LIQUIDITY_SWEEP_COMPATIBLE",
                "FAIR_VALUE_GAP_PRESENT",
                "STRUCTURE_EVENT_ALIGNED",
            ),
        },
        {
            "candidate": "BEARISH_LIQUIDITY_SWEEP_COMPATIBLE",
            "direction": MethodologyDirection.BEARISH,
            "condition": "LIQUIDITY_SWEEP_COMPATIBLE",
            "positive_label": "COMPATIBLE",
            "negative_label": "NOT_COMPATIBLE",
            "controls": (
                "ORDER_BLOCK_PRESENT",
                "FAIR_VALUE_GAP_PRESENT",
                "STRUCTURE_EVENT_ALIGNED",
            ),
        },
    )

    _CSV_COLUMNS: Final[tuple[str, ...]] = (
        "Candidate",
        "Direction",
        "Horizon Bars",
        "Comparison Scope",
        "Fold Number",
        "Control Condition",
        "Control State",
        "Positive Cohort Label",
        "Negative Cohort Label",
        "Positive Sample Count",
        "Negative Sample Count",
        "Positive Favorable Rate",
        "Negative Favorable Rate",
        "Favorable Rate Delta",
        "Positive Average Return Percent",
        "Negative Average Return Percent",
        "Average Return Delta Percent",
        "Positive MFE MAE Ratio",
        "Negative MFE MAE Ratio",
        "Sample Warning",
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
        payload, rows = self.calculate(
            observations,
            evaluations,
            window_metadata=window_metadata,
        )

        csv_path = self.output_directory / "methodology_counterfactual_cohorts.csv"
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

        json_path = self.output_directory / "methodology_counterfactual_cohorts.json"
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
        observations_tuple = self._validate_observations(observations)
        evaluations_tuple = self._validate_evaluations(evaluations)
        metadata = self._validate_window_metadata(window_metadata)

        observation_index = {
            item.timestamp.astimezone(UTC): item
            for item in observations_tuple
        }
        usable = tuple(
            item
            for item in evaluations_tuple
            if item.methodology is MethodologyIdentifier.SMC
            and item.horizon_complete
            and item.horizon_bars in self.HORIZONS
            and item.direction
            in {
                MethodologyDirection.BULLISH,
                MethodologyDirection.BEARISH,
            }
        )
        missing = sorted(
            {
                item.observation_timestamp.astimezone(UTC)
                for item in usable
                if item.observation_timestamp.astimezone(UTC)
                not in observation_index
            }
        )
        if missing:
            raise ValueError(
                "outcome evaluations contain timestamps without matching "
                "methodology observations"
            )

        timestamps = tuple(
            sorted({item.observation_timestamp.astimezone(UTC) for item in usable})
        )
        folds = self._build_folds(timestamps)

        rows: list[dict[str, object]] = []
        candidate_payloads: list[dict[str, object]] = []

        for candidate in self.CANDIDATES:
            direction = candidate["direction"]
            candidate_evaluations = tuple(
                item for item in usable if item.direction is direction
            )
            aggregate_rows = self._comparison_rows(
                candidate,
                candidate_evaluations,
                observation_index,
                scope="AGGREGATE",
            )
            rows.extend(aggregate_rows)

            fold_rows: list[dict[str, object]] = []
            for fold_number, fold_timestamps in enumerate(folds, start=1):
                allowed = set(fold_timestamps)
                subset = tuple(
                    item
                    for item in candidate_evaluations
                    if item.observation_timestamp.astimezone(UTC) in allowed
                )
                current = self._comparison_rows(
                    candidate,
                    subset,
                    observation_index,
                    scope="FOLD",
                    fold_number=fold_number,
                )
                fold_rows.extend(current)
                rows.extend(current)

            stratified_rows: list[dict[str, object]] = []
            for control in candidate["controls"]:
                for state in ("SATISFIED", "FAILED"):
                    subset = tuple(
                        item
                        for item in candidate_evaluations
                        if self._condition_state(
                            observation_index[
                                item.observation_timestamp.astimezone(UTC)
                            ].smc,
                            str(control),
                        )
                        == state
                    )
                    current = self._comparison_rows(
                        candidate,
                        subset,
                        observation_index,
                        scope="STRATIFIED",
                        control_condition=str(control),
                        control_state=state,
                    )
                    stratified_rows.extend(current)
                    rows.extend(current)

            candidate_payloads.append(
                {
                    "candidate": candidate["candidate"],
                    "direction": direction.value,
                    "condition": candidate["condition"],
                    "positive_cohort_label": candidate["positive_label"],
                    "negative_cohort_label": candidate["negative_label"],
                    "aggregate_comparisons": aggregate_rows,
                    "fold_comparisons": fold_rows,
                    "stratified_comparisons": stratified_rows,
                    "composition": self._composition(
                        candidate,
                        candidate_evaluations,
                        observation_index,
                    ),
                    "overlap_rates": self._overlap(
                        candidate,
                        candidate_evaluations,
                        observation_index,
                    ),
                    "stability_summary": self._stability_summary(
                        candidate,
                        aggregate_rows,
                        fold_rows,
                    ),
                }
            )

        payload: dict[str, object] = {
            "window_metadata": metadata,
            "fold_count": self.fold_count,
            "minimum_sample_size": self.minimum_sample_size,
            "horizons": list(self.HORIZONS),
            "observation_count": len(observations_tuple),
            "evaluation_count": len(evaluations_tuple),
            "usable_smc_evaluation_count": len(usable),
            "candidates": candidate_payloads,
            "observational_only": True,
            "trade_authority": False,
            "methodology_rules_modified": False,
            "future_information_used_for_research_only": True,
        }
        return payload, rows

    def _comparison_rows(
        self,
        candidate: Mapping[str, object],
        evaluations: tuple[MethodologyOutcomeEvaluation, ...],
        observation_index: Mapping[datetime, MethodologyObservation],
        *,
        scope: str,
        fold_number: int | None = None,
        control_condition: str | None = None,
        control_state: str | None = None,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        condition = str(candidate["condition"])

        for horizon in self.HORIZONS:
            positive: list[MethodologyOutcomeEvaluation] = []
            negative: list[MethodologyOutcomeEvaluation] = []
            for item in evaluations:
                if item.horizon_bars != horizon:
                    continue
                observation = observation_index[
                    item.observation_timestamp.astimezone(UTC)
                ]
                state = self._condition_state(observation.smc, condition)
                if state == "SATISFIED":
                    positive.append(item)
                elif state == "FAILED":
                    negative.append(item)

            positive_stats = self._statistics(positive)
            negative_stats = self._statistics(negative)
            rows.append(
                {
                    "Candidate": candidate["candidate"],
                    "Direction": candidate["direction"].value,
                    "Horizon Bars": horizon,
                    "Comparison Scope": scope,
                    "Fold Number": fold_number,
                    "Control Condition": control_condition,
                    "Control State": control_state,
                    "Positive Cohort Label": candidate["positive_label"],
                    "Negative Cohort Label": candidate["negative_label"],
                    "Positive Sample Count": len(positive),
                    "Negative Sample Count": len(negative),
                    "Positive Favorable Rate": positive_stats["favorable_rate"],
                    "Negative Favorable Rate": negative_stats["favorable_rate"],
                    "Favorable Rate Delta": self._difference(
                        positive_stats["favorable_rate"],
                        negative_stats["favorable_rate"],
                    ),
                    "Positive Average Return Percent": positive_stats[
                        "average_return_percent"
                    ],
                    "Negative Average Return Percent": negative_stats[
                        "average_return_percent"
                    ],
                    "Average Return Delta Percent": self._difference(
                        positive_stats["average_return_percent"],
                        negative_stats["average_return_percent"],
                    ),
                    "Positive MFE MAE Ratio": positive_stats["mfe_mae_ratio"],
                    "Negative MFE MAE Ratio": negative_stats["mfe_mae_ratio"],
                    "Sample Warning": self._sample_warning(
                        len(positive),
                        len(negative),
                    ),
                }
            )
        return rows

    def _composition(
        self,
        candidate: Mapping[str, object],
        evaluations: tuple[MethodologyOutcomeEvaluation, ...],
        observation_index: Mapping[datetime, MethodologyObservation],
    ) -> dict[str, object]:
        condition = str(candidate["condition"])
        timestamps = {
            item.observation_timestamp.astimezone(UTC)
            for item in evaluations
        }
        result: dict[str, object] = {}

        for state, label in (
            ("SATISFIED", str(candidate["positive_label"])),
            ("FAILED", str(candidate["negative_label"])),
        ):
            cohort = tuple(
                timestamp
                for timestamp in timestamps
                if self._condition_state(
                    observation_index[timestamp].smc,
                    condition,
                )
                == state
            )
            sessions = Counter()
            regimes = Counter()
            for timestamp in cohort:
                context = observation_index[timestamp].context
                sessions[context.session_name or "OFF_SESSION"] += 1
                regimes[context.regime_name or "MISSING"] += 1
            result[label] = {
                "observation_count": len(cohort),
                "session_counts": dict(sorted(sessions.items())),
                "regime_counts": dict(sorted(regimes.items())),
            }
        return result

    def _overlap(
        self,
        candidate: Mapping[str, object],
        evaluations: tuple[MethodologyOutcomeEvaluation, ...],
        observation_index: Mapping[datetime, MethodologyObservation],
    ) -> list[dict[str, object]]:
        condition = str(candidate["condition"])
        timestamps = {
            item.observation_timestamp.astimezone(UTC)
            for item in evaluations
        }
        rows: list[dict[str, object]] = []

        for state, label in (
            ("SATISFIED", str(candidate["positive_label"])),
            ("FAILED", str(candidate["negative_label"])),
        ):
            cohort = tuple(
                timestamp
                for timestamp in timestamps
                if self._condition_state(
                    observation_index[timestamp].smc,
                    condition,
                )
                == state
            )
            for control in candidate["controls"]:
                count = sum(
                    self._condition_state(
                        observation_index[timestamp].smc,
                        str(control),
                    )
                    == "SATISFIED"
                    for timestamp in cohort
                )
                rows.append(
                    {
                        "cohort": label,
                        "control_condition": control,
                        "cohort_observation_count": len(cohort),
                        "control_satisfied_count": count,
                        "control_satisfied_rate": (
                            count / len(cohort) if cohort else None
                        ),
                    }
                )
        return rows

    def _stability_summary(
        self,
        candidate: Mapping[str, object],
        aggregate_rows: list[dict[str, object]],
        fold_rows: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        summaries: list[dict[str, object]] = []

        for horizon in self.HORIZONS:
            aggregate = next(
                row
                for row in aggregate_rows
                if row["Horizon Bars"] == horizon
            )
            valid = [
                row
                for row in fold_rows
                if row["Horizon Bars"] == horizon
                and not row["Sample Warning"]
                and row["Favorable Rate Delta"] is not None
                and row["Average Return Delta Percent"] is not None
            ]
            positive_favorable = sum(
                float(row["Favorable Rate Delta"]) > 0.0 for row in valid
            )
            positive_return = sum(
                float(row["Average Return Delta Percent"]) > 0.0
                for row in valid
            )
            warnings: list[str] = []
            if len(valid) < self.fold_count:
                warnings.append("INSUFFICIENT_VALID_FOLDS")
            if not valid:
                warnings.append("NO_VALID_FOLDS")
            else:
                if positive_favorable not in {0, len(valid)}:
                    warnings.append("FAVORABLE_RATE_SIGN_UNSTABLE")
                if positive_return not in {0, len(valid)}:
                    warnings.append("RETURN_SIGN_UNSTABLE")

            summaries.append(
                {
                    "candidate": candidate["candidate"],
                    "horizon_bars": horizon,
                    "aggregate_favorable_rate_delta": aggregate[
                        "Favorable Rate Delta"
                    ],
                    "aggregate_return_delta_percent": aggregate[
                        "Average Return Delta Percent"
                    ],
                    "valid_fold_count": len(valid),
                    "positive_favorable_delta_folds": positive_favorable,
                    "positive_return_delta_folds": positive_return,
                    "warnings": warnings,
                }
            )
        return summaries

    @staticmethod
    def _condition_state(
        result: MethodologyResult,
        condition_code: str,
    ) -> str:
        for condition in result.satisfied_conditions:
            if condition.code == condition_code:
                return "SATISFIED"
        for condition in result.failed_conditions:
            if condition.code == condition_code:
                return "FAILED"
        for condition in result.unavailable_conditions:
            if condition.code == condition_code:
                return "UNAVAILABLE"
        return "NOT_RECORDED"

    @staticmethod
    def _statistics(
        evaluations: Sequence[MethodologyOutcomeEvaluation],
    ) -> dict[str, float | None]:
        if not evaluations:
            return {
                "favorable_rate": None,
                "average_return_percent": None,
                "mfe_mae_ratio": None,
            }

        count = len(evaluations)
        average_mfe = sum(
            float(item.maximum_favorable_excursion)
            for item in evaluations
        ) / count
        average_mae = sum(
            float(item.maximum_adverse_excursion)
            for item in evaluations
        ) / count
        return {
            "favorable_rate": sum(
                item.favorable_terminal_outcome is True
                for item in evaluations
            ) / count,
            "average_return_percent": sum(
                float(item.directional_return_pct)
                for item in evaluations
            ) / count,
            "mfe_mae_ratio": (
                average_mfe / average_mae
                if average_mae > 0.0
                else None
            ),
        }

    def _sample_warning(
        self,
        positive_count: int,
        negative_count: int,
    ) -> str:
        warnings: list[str] = []
        if positive_count == 0:
            warnings.append("NO_POSITIVE_COHORT_SAMPLE")
        elif positive_count < self.minimum_sample_size:
            warnings.append("INSUFFICIENT_POSITIVE_COHORT_SAMPLE")
        if negative_count == 0:
            warnings.append("NO_NEGATIVE_COHORT_SAMPLE")
        elif negative_count < self.minimum_sample_size:
            warnings.append("INSUFFICIENT_NEGATIVE_COHORT_SAMPLE")
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
