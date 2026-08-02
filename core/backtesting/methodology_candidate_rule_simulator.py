"""Report-only simulation of frozen methodology candidate rules."""

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
    MethodologyEvaluationStatus,
    MethodologyIdentifier,
    MethodologyResult,
)

from .methodology_observer import MethodologyObservation
from .methodology_outcome_research import MethodologyOutcomeEvaluation


class MethodologyCandidateRuleSimulator:
    """Compare frozen experimental cohorts with current SMC populations."""

    DEFAULT_FOLD_COUNT: Final[int] = 5
    DEFAULT_MINIMUM_SAMPLE_SIZE: Final[int] = 30
    HORIZONS: Final[tuple[int, ...]] = (12, 24)

    VARIANTS: Final[tuple[dict[str, object], ...]] = (
        {
            "variant": "VARIANT_A_BULLISH_ORDER_BLOCK_STRUCTURE",
            "direction": MethodologyDirection.BULLISH,
            "required_satisfied": (
                "ORDER_BLOCK_PRESENT",
                "STRUCTURE_EVENT_ALIGNED",
            ),
            "required_failed": (),
            "description": (
                "Bullish observations with order block present and "
                "structure event aligned."
            ),
        },
        {
            "variant": "VARIANT_B_BEARISH_EXCLUDE_COMPATIBLE_SWEEP",
            "direction": MethodologyDirection.BEARISH,
            "required_satisfied": (),
            "required_failed": ("LIQUIDITY_SWEEP_COMPATIBLE",),
            "description": (
                "Bearish observations excluding liquidity-sweep-compatible "
                "observations."
            ),
        },
    )

    _CSV_COLUMNS: Final[tuple[str, ...]] = (
        "Variant",
        "Direction",
        "Horizon Bars",
        "Scope",
        "Fold Number",
        "Population",
        "Sample Count",
        "Favorable Rate",
        "Average Return Percent",
        "MFE MAE Ratio",
        "Variant Minus Confirmed Favorable Delta",
        "Variant Minus Confirmed Return Delta Percent",
        "Variant Minus Baseline Favorable Delta",
        "Variant Minus Baseline Return Delta Percent",
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

        csv_path = (
            self.output_directory
            / "methodology_candidate_rule_simulation.csv"
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
            / "methodology_candidate_rule_simulation.json"
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

        csv_rows: list[dict[str, object]] = []
        variant_payloads: list[dict[str, object]] = []

        for variant in self.VARIANTS:
            direction = variant["direction"]
            direction_evaluations = tuple(
                item for item in usable if item.direction is direction
            )
            direction_timestamps = tuple(
                sorted(
                    {
                        item.observation_timestamp.astimezone(UTC)
                        for item in direction_evaluations
                    }
                )
            )
            direction_folds = self._build_folds(direction_timestamps)

            aggregate = self._evaluate_scope(
                variant,
                direction_evaluations,
                observation_index,
                scope="AGGREGATE",
            )
            csv_rows.extend(aggregate["rows"])

            fold_results: list[dict[str, object]] = []
            for fold_number, fold_timestamps in enumerate(
                direction_folds,
                start=1,
            ):
                allowed = set(fold_timestamps)
                subset = tuple(
                    item
                    for item in direction_evaluations
                    if item.observation_timestamp.astimezone(UTC) in allowed
                )
                result = self._evaluate_scope(
                    variant,
                    subset,
                    observation_index,
                    scope="FOLD",
                    fold_number=fold_number,
                )
                fold_results.append(result)
                csv_rows.extend(result["rows"])

            variant_timestamps = self._variant_timestamps(
                variant,
                direction_evaluations,
                observation_index,
            )
            confirmed_timestamps = {
                item.observation_timestamp.astimezone(UTC)
                for item in direction_evaluations
                if item.evaluation_status
                is MethodologyEvaluationStatus.CONFIRMED
            }
            baseline_timestamps = {
                item.observation_timestamp.astimezone(UTC)
                for item in direction_evaluations
            }

            variant_payloads.append(
                {
                    "variant": variant["variant"],
                    "description": variant["description"],
                    "direction": direction.value,
                    "required_satisfied_conditions": list(
                        variant["required_satisfied"]
                    ),
                    "required_failed_conditions": list(
                        variant["required_failed"]
                    ),
                    "fold_partitioning": {
                        "basis": "DIRECTION_SPECIFIC_TIMESTAMPS",
                        "direction_timestamp_count": len(
                            direction_timestamps
                        ),
                        "requested_fold_count": self.fold_count,
                        "fold_timestamp_counts": [
                            len(fold) for fold in direction_folds
                        ],
                    },
                    "aggregate": aggregate,
                    "folds": fold_results,
                    "retention": {
                        "variant_observation_count": len(variant_timestamps),
                        "confirmed_observation_count": len(
                            confirmed_timestamps
                        ),
                        "direction_baseline_observation_count": len(
                            baseline_timestamps
                        ),
                        "variant_vs_confirmed_retention": (
                            len(variant_timestamps)
                            / len(confirmed_timestamps)
                            if confirmed_timestamps
                            else None
                        ),
                        "variant_vs_direction_baseline_retention": (
                            len(variant_timestamps)
                            / len(baseline_timestamps)
                            if baseline_timestamps
                            else None
                        ),
                    },
                    "composition": self._composition(
                        variant_timestamps,
                        observation_index,
                    ),
                    "stability": self._stability(
                        aggregate,
                        fold_results,
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
            "fold_partitioning": "DIRECTION_SPECIFIC_TIMESTAMPS",
            "variants": variant_payloads,
            "observational_only": True,
            "trade_authority": False,
            "methodology_rules_modified": False,
            "active_pipeline_modified": False,
            "future_information_used_for_research_only": True,
        }
        return payload, csv_rows

    def _evaluate_scope(
        self,
        variant: Mapping[str, object],
        evaluations: tuple[MethodologyOutcomeEvaluation, ...],
        observation_index: Mapping[datetime, MethodologyObservation],
        *,
        scope: str,
        fold_number: int | None = None,
    ) -> dict[str, object]:
        rows: list[dict[str, object]] = []
        horizon_results: list[dict[str, object]] = []

        for horizon in self.HORIZONS:
            horizon_items = tuple(
                item for item in evaluations if item.horizon_bars == horizon
            )
            variant_items = tuple(
                item
                for item in horizon_items
                if self._matches_variant(
                    variant,
                    observation_index[
                        item.observation_timestamp.astimezone(UTC)
                    ].smc,
                )
            )
            confirmed_items = tuple(
                item
                for item in horizon_items
                if item.evaluation_status
                is MethodologyEvaluationStatus.CONFIRMED
            )
            baseline_items = horizon_items

            stats = {
                "VARIANT": self._statistics(variant_items),
                "SMC_CONFIRMED": self._statistics(confirmed_items),
                "DIRECTION_BASELINE": self._statistics(baseline_items),
            }
            counts = {
                "VARIANT": len(variant_items),
                "SMC_CONFIRMED": len(confirmed_items),
                "DIRECTION_BASELINE": len(baseline_items),
            }
            warning = self._sample_warning(counts)

            variant_stats = stats["VARIANT"]
            confirmed_stats = stats["SMC_CONFIRMED"]
            baseline_stats = stats["DIRECTION_BASELINE"]

            comparison = {
                "horizon_bars": horizon,
                "sample_counts": counts,
                "statistics": stats,
                "variant_minus_confirmed_favorable_delta": self._difference(
                    variant_stats["favorable_rate"],
                    confirmed_stats["favorable_rate"],
                ),
                "variant_minus_confirmed_return_delta_percent": self._difference(
                    variant_stats["average_return_percent"],
                    confirmed_stats["average_return_percent"],
                ),
                "variant_minus_baseline_favorable_delta": self._difference(
                    variant_stats["favorable_rate"],
                    baseline_stats["favorable_rate"],
                ),
                "variant_minus_baseline_return_delta_percent": self._difference(
                    variant_stats["average_return_percent"],
                    baseline_stats["average_return_percent"],
                ),
                "sample_warning": warning,
            }
            horizon_results.append(comparison)

            for population in (
                "VARIANT",
                "SMC_CONFIRMED",
                "DIRECTION_BASELINE",
            ):
                population_stats = stats[population]
                rows.append(
                    {
                        "Variant": variant["variant"],
                        "Direction": variant["direction"].value,
                        "Horizon Bars": horizon,
                        "Scope": scope,
                        "Fold Number": fold_number,
                        "Population": population,
                        "Sample Count": counts[population],
                        "Favorable Rate": population_stats["favorable_rate"],
                        "Average Return Percent": population_stats[
                            "average_return_percent"
                        ],
                        "MFE MAE Ratio": population_stats["mfe_mae_ratio"],
                        "Variant Minus Confirmed Favorable Delta": comparison[
                            "variant_minus_confirmed_favorable_delta"
                        ],
                        "Variant Minus Confirmed Return Delta Percent": comparison[
                            "variant_minus_confirmed_return_delta_percent"
                        ],
                        "Variant Minus Baseline Favorable Delta": comparison[
                            "variant_minus_baseline_favorable_delta"
                        ],
                        "Variant Minus Baseline Return Delta Percent": comparison[
                            "variant_minus_baseline_return_delta_percent"
                        ],
                        "Sample Warning": warning,
                    }
                )

        return {
            "scope": scope,
            "fold_number": fold_number,
            "horizons": horizon_results,
            "rows": rows,
        }

    def _variant_timestamps(
        self,
        variant: Mapping[str, object],
        evaluations: tuple[MethodologyOutcomeEvaluation, ...],
        observation_index: Mapping[datetime, MethodologyObservation],
    ) -> set[datetime]:
        return {
            item.observation_timestamp.astimezone(UTC)
            for item in evaluations
            if self._matches_variant(
                variant,
                observation_index[
                    item.observation_timestamp.astimezone(UTC)
                ].smc,
            )
        }

    def _matches_variant(
        self,
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
    def _composition(
        timestamps: set[datetime],
        observation_index: Mapping[datetime, MethodologyObservation],
    ) -> dict[str, object]:
        sessions = Counter()
        regimes = Counter()
        for timestamp in timestamps:
            context = observation_index[timestamp].context
            sessions[context.session_name or "OFF_SESSION"] += 1
            regimes[context.regime_name or "MISSING"] += 1
        return {
            "observation_count": len(timestamps),
            "session_counts": dict(sorted(sessions.items())),
            "regime_counts": dict(sorted(regimes.items())),
        }

    def _stability(
        self,
        aggregate: Mapping[str, object],
        folds: Sequence[Mapping[str, object]],
    ) -> list[dict[str, object]]:
        summaries: list[dict[str, object]] = []
        for horizon in self.HORIZONS:
            aggregate_result = next(
                item
                for item in aggregate["horizons"]
                if item["horizon_bars"] == horizon
            )
            fold_results = [
                next(
                    item
                    for item in fold["horizons"]
                    if item["horizon_bars"] == horizon
                )
                for fold in folds
            ]
            valid = [
                item
                for item in fold_results
                if not item["sample_warning"]
                and item[
                    "variant_minus_baseline_favorable_delta"
                ]
                is not None
                and item[
                    "variant_minus_baseline_return_delta_percent"
                ]
                is not None
            ]
            positive_favorable = sum(
                float(
                    item["variant_minus_baseline_favorable_delta"]
                )
                > 0.0
                for item in valid
            )
            positive_return = sum(
                float(
                    item[
                        "variant_minus_baseline_return_delta_percent"
                    ]
                )
                > 0.0
                for item in valid
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
                    "horizon_bars": horizon,
                    "aggregate_variant_minus_baseline_favorable_delta": (
                        aggregate_result[
                            "variant_minus_baseline_favorable_delta"
                        ]
                    ),
                    "aggregate_variant_minus_baseline_return_delta_percent": (
                        aggregate_result[
                            "variant_minus_baseline_return_delta_percent"
                        ]
                    ),
                    "valid_fold_count": len(valid),
                    "positive_favorable_delta_folds": positive_favorable,
                    "positive_return_delta_folds": positive_return,
                    "warnings": warnings,
                }
            )
        return summaries

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
            )
            / count,
            "average_return_percent": sum(
                float(item.directional_return_pct)
                for item in evaluations
            )
            / count,
            "mfe_mae_ratio": (
                average_mfe / average_mae
                if average_mae > 0.0
                else None
            ),
        }

    def _sample_warning(
        self,
        counts: Mapping[str, int],
    ) -> str:
        warnings: list[str] = []
        for population, count in counts.items():
            if count == 0:
                warnings.append(f"NO_{population}_SAMPLE")
            elif count < self.minimum_sample_size:
                warnings.append(f"INSUFFICIENT_{population}_SAMPLE")
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
