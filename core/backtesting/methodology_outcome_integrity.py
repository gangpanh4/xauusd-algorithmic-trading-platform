"""Integrity and baseline-comparison diagnostics for methodology outcomes."""

from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from core.regime_detector.models import MarketBar
from core.strategies.methodology_models import (
    MethodologyDirection,
    MethodologyEvaluationStatus,
    MethodologyIdentifier,
)

from .methodology_observer import MethodologyObservation
from .methodology_outcome_research import MethodologyOutcomeEvaluation


class MethodologyOutcomeIntegrityAnalytics:
    """Audit outcome provenance and compare confirmations with baselines."""

    MINIMUM_SAMPLE_SIZE: Final[int] = 30

    _COMPARISON_COLUMNS: Final[tuple[str, ...]] = (
        "Methodology",
        "Direction",
        "Horizon Bars",
        "Confirmed Sample Count",
        "Baseline Sample Count",
        "Confirmed Favorable Rate",
        "Baseline Favorable Rate",
        "Favorable Rate Delta",
        "Confirmed Average Return Percent",
        "Baseline Average Return Percent",
        "Average Return Delta Percent",
        "Confirmed Average MFE",
        "Baseline Average MFE",
        "Confirmed Average MAE",
        "Baseline Average MAE",
        "Confirmed MFE MAE Ratio",
        "Baseline MFE MAE Ratio",
        "Sample Warning",
    )

    def __init__(
        self,
        output_directory: str | Path = "output/backtests",
        *,
        minimum_sample_size: int = MINIMUM_SAMPLE_SIZE,
    ) -> None:
        if isinstance(minimum_sample_size, bool) or not isinstance(
            minimum_sample_size,
            int,
        ):
            raise TypeError("minimum_sample_size must be an integer")
        if minimum_sample_size <= 0:
            raise ValueError("minimum_sample_size must be greater than zero")
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.minimum_sample_size = minimum_sample_size

    def export(
        self,
        observations: Sequence[MethodologyObservation],
        m5_bars: Sequence[MarketBar],
        evaluations: Sequence[MethodologyOutcomeEvaluation],
        *,
        horizons: Sequence[int],
    ) -> tuple[Path, Path, Path]:
        """Write integrity JSON and aggregate comparison CSV/JSON."""

        integrity = self.calculate_integrity(
            observations,
            m5_bars,
            evaluations,
            horizons=horizons,
        )
        comparisons = self.calculate_comparisons(evaluations)

        integrity_path = (
            self.output_directory / "methodology_outcome_integrity.json"
        )
        integrity_path.write_text(
            json.dumps(integrity, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        comparison_csv_path = (
            self.output_directory / "methodology_outcome_comparison.csv"
        )
        with comparison_csv_path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=list(self._COMPARISON_COLUMNS),
                extrasaction="raise",
            )
            writer.writeheader()
            writer.writerows(comparisons)

        comparison_json_path = (
            self.output_directory / "methodology_outcome_comparison.json"
        )
        comparison_json_path.write_text(
            json.dumps(
                {
                    "minimum_sample_size": self.minimum_sample_size,
                    "comparisons": comparisons,
                    "observational_only": True,
                    "trade_authority": False,
                    "future_information_used_for_research_only": True,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return integrity_path, comparison_csv_path, comparison_json_path

    @classmethod
    def calculate_integrity(
        cls,
        observations: Sequence[MethodologyObservation],
        m5_bars: Sequence[MarketBar],
        evaluations: Sequence[MethodologyOutcomeEvaluation],
        *,
        horizons: Sequence[int],
    ) -> dict[str, object]:
        """Return deterministic provenance and coverage diagnostics."""

        validated_observations = cls._validate_observations(observations)
        validated_bars = cls._validate_bars(m5_bars)
        validated_evaluations = cls._validate_evaluations(evaluations)
        validated_horizons = cls._validate_horizons(horizons)

        bar_timestamps = {
            bar.timestamp.astimezone(UTC) for bar in validated_bars
        }
        observation_timestamps = tuple(
            observation.timestamp.astimezone(UTC)
            for observation in validated_observations
        )
        matched = tuple(
            timestamp
            for timestamp in observation_timestamps
            if timestamp in bar_timestamps
        )
        unmatched = tuple(
            timestamp
            for timestamp in observation_timestamps
            if timestamp not in bar_timestamps
        )

        expected_evaluations = (
            len(validated_observations)
            * len(MethodologyIdentifier)
            * len(validated_horizons)
        )
        complete_by_horizon = {
            str(horizon): 0 for horizon in validated_horizons
        }
        incomplete_by_horizon = {
            str(horizon): 0 for horizon in validated_horizons
        }
        directional_by_horizon = {
            str(horizon): 0 for horizon in validated_horizons
        }
        nondirectional_by_horizon = {
            str(horizon): 0 for horizon in validated_horizons
        }

        for evaluation in validated_evaluations:
            key = str(evaluation.horizon_bars)
            if key not in complete_by_horizon:
                raise ValueError(
                    "evaluation horizon is not present in configured horizons"
                )
            if evaluation.horizon_complete:
                complete_by_horizon[key] += 1
            else:
                incomplete_by_horizon[key] += 1
            if evaluation.direction in {
                MethodologyDirection.BULLISH,
                MethodologyDirection.BEARISH,
            }:
                directional_by_horizon[key] += 1
            else:
                nondirectional_by_horizon[key] += 1

        warnings: list[str] = []
        if unmatched:
            warnings.append("UNMATCHED_OBSERVATION_TIMESTAMPS")
        if len(validated_evaluations) != expected_evaluations:
            warnings.append("EVALUATION_COUNT_MISMATCH")
        if any(incomplete_by_horizon.values()):
            warnings.append("INCOMPLETE_TAIL_HORIZONS")
        if not validated_bars and validated_observations:
            warnings.append("MISSING_M5_HISTORY")

        return {
            "methodology_observation_count": len(validated_observations),
            "m5_bar_count": len(validated_bars),
            "configured_horizons": list(validated_horizons),
            "methodologies_per_observation": len(MethodologyIdentifier),
            "expected_evaluation_count": expected_evaluations,
            "actual_evaluation_count": len(validated_evaluations),
            "evaluation_count_matches": (
                len(validated_evaluations) == expected_evaluations
            ),
            "exact_timestamp_match_count": len(matched),
            "unmatched_observation_count": len(unmatched),
            "unmatched_observation_timestamps": [
                timestamp.isoformat() for timestamp in unmatched
            ],
            "observation_first_timestamp": cls._first_timestamp(
                observation_timestamps
            ),
            "observation_last_timestamp": cls._last_timestamp(
                observation_timestamps
            ),
            "m5_first_timestamp": cls._first_timestamp(
                tuple(sorted(bar_timestamps))
            ),
            "m5_last_timestamp": cls._last_timestamp(
                tuple(sorted(bar_timestamps))
            ),
            "complete_evaluations_by_horizon": complete_by_horizon,
            "incomplete_evaluations_by_horizon": incomplete_by_horizon,
            "directional_evaluations_by_horizon": directional_by_horizon,
            "nondirectional_evaluations_by_horizon": nondirectional_by_horizon,
            "warnings": warnings,
            "observational_only": True,
            "trade_authority": False,
            "future_information_used_for_research_only": True,
        }

    def calculate_comparisons(
        self,
        evaluations: Sequence[MethodologyOutcomeEvaluation],
    ) -> list[dict[str, object]]:
        """Compare confirmed outcomes with NOT_CONFIRMED baselines."""

        validated = self._validate_evaluations(evaluations)
        buckets: dict[
            tuple[
                MethodologyIdentifier,
                MethodologyDirection,
                int,
                MethodologyEvaluationStatus,
            ],
            dict[str, float | int],
        ] = {}

        for item in validated:
            if not item.horizon_complete:
                continue
            if item.direction not in {
                MethodologyDirection.BULLISH,
                MethodologyDirection.BEARISH,
            }:
                continue
            if item.evaluation_status not in {
                MethodologyEvaluationStatus.CONFIRMED,
                MethodologyEvaluationStatus.NOT_CONFIRMED,
            }:
                continue

            key = (
                item.methodology,
                item.direction,
                item.horizon_bars,
                item.evaluation_status,
            )
            bucket = buckets.setdefault(
                key,
                {
                    "sample_count": 0,
                    "favorable_count": 0,
                    "return_sum": 0.0,
                    "mfe_sum": 0.0,
                    "mae_sum": 0.0,
                },
            )
            bucket["sample_count"] = int(bucket["sample_count"]) + 1
            bucket["favorable_count"] = (
                int(bucket["favorable_count"])
                + int(bool(item.favorable_terminal_outcome))
            )
            bucket["return_sum"] = float(bucket["return_sum"]) + float(
                item.directional_return_pct
            )
            bucket["mfe_sum"] = float(bucket["mfe_sum"]) + float(
                item.maximum_favorable_excursion
            )
            bucket["mae_sum"] = float(bucket["mae_sum"]) + float(
                item.maximum_adverse_excursion
            )

        group_keys = sorted(
            {
                (methodology, direction, horizon)
                for methodology, direction, horizon, _ in buckets
            },
            key=lambda value: (
                value[0].value,
                value[1].value,
                value[2],
            ),
        )

        rows: list[dict[str, object]] = []
        for methodology, direction, horizon in group_keys:
            confirmed = buckets.get(
                (
                    methodology,
                    direction,
                    horizon,
                    MethodologyEvaluationStatus.CONFIRMED,
                )
            )
            baseline = buckets.get(
                (
                    methodology,
                    direction,
                    horizon,
                    MethodologyEvaluationStatus.NOT_CONFIRMED,
                )
            )
            confirmed_stats = self._finalize_bucket(confirmed)
            baseline_stats = self._finalize_bucket(baseline)
            warning = self._sample_warning(
                confirmed_stats["sample_count"],
                baseline_stats["sample_count"],
            )

            rows.append(
                {
                    "Methodology": methodology.value,
                    "Direction": direction.value,
                    "Horizon Bars": horizon,
                    "Confirmed Sample Count": confirmed_stats["sample_count"],
                    "Baseline Sample Count": baseline_stats["sample_count"],
                    "Confirmed Favorable Rate": confirmed_stats[
                        "favorable_rate"
                    ],
                    "Baseline Favorable Rate": baseline_stats[
                        "favorable_rate"
                    ],
                    "Favorable Rate Delta": self._difference(
                        confirmed_stats["favorable_rate"],
                        baseline_stats["favorable_rate"],
                    ),
                    "Confirmed Average Return Percent": confirmed_stats[
                        "average_return_pct"
                    ],
                    "Baseline Average Return Percent": baseline_stats[
                        "average_return_pct"
                    ],
                    "Average Return Delta Percent": self._difference(
                        confirmed_stats["average_return_pct"],
                        baseline_stats["average_return_pct"],
                    ),
                    "Confirmed Average MFE": confirmed_stats["average_mfe"],
                    "Baseline Average MFE": baseline_stats["average_mfe"],
                    "Confirmed Average MAE": confirmed_stats["average_mae"],
                    "Baseline Average MAE": baseline_stats["average_mae"],
                    "Confirmed MFE MAE Ratio": confirmed_stats[
                        "mfe_mae_ratio"
                    ],
                    "Baseline MFE MAE Ratio": baseline_stats[
                        "mfe_mae_ratio"
                    ],
                    "Sample Warning": warning,
                }
            )
        return rows

    def _sample_warning(
        self,
        confirmed_count: int,
        baseline_count: int,
    ) -> str:
        warnings: list[str] = []
        if confirmed_count == 0:
            warnings.append("NO_CONFIRMED_SAMPLE")
        elif confirmed_count < self.minimum_sample_size:
            warnings.append("INSUFFICIENT_CONFIRMED_SAMPLE")
        if baseline_count == 0:
            warnings.append("NO_BASELINE_SAMPLE")
        elif baseline_count < self.minimum_sample_size:
            warnings.append("INSUFFICIENT_BASELINE_SAMPLE")
        return "|".join(warnings)

    @staticmethod
    def _finalize_bucket(
        bucket: dict[str, float | int] | None,
    ) -> dict[str, float | int | None]:
        if bucket is None:
            return {
                "sample_count": 0,
                "favorable_rate": None,
                "average_return_pct": None,
                "average_mfe": None,
                "average_mae": None,
                "mfe_mae_ratio": None,
            }
        sample_count = int(bucket["sample_count"])
        if sample_count <= 0:
            raise ValueError("outcome aggregate sample count must be positive")
        average_mfe = float(bucket["mfe_sum"]) / sample_count
        average_mae = float(bucket["mae_sum"]) / sample_count
        return {
            "sample_count": sample_count,
            "favorable_rate": (
                int(bucket["favorable_count"]) / sample_count
            ),
            "average_return_pct": (
                float(bucket["return_sum"]) / sample_count
            ),
            "average_mfe": average_mfe,
            "average_mae": average_mae,
            "mfe_mae_ratio": (
                average_mfe / average_mae
                if average_mae > 0.0
                else None
            ),
        }

    @staticmethod
    def _difference(
        left: float | int | None,
        right: float | int | None,
    ) -> float | None:
        if left is None or right is None:
            return None
        return float(left) - float(right)

    @staticmethod
    def _first_timestamp(values: tuple[datetime, ...]) -> str | None:
        return values[0].isoformat() if values else None

    @staticmethod
    def _last_timestamp(values: tuple[datetime, ...]) -> str | None:
        return values[-1].isoformat() if values else None

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
        timestamps = tuple(
            item.timestamp.astimezone(UTC) for item in validated
        )
        if timestamps != tuple(sorted(timestamps)):
            raise ValueError(
                "methodology observations must be chronologically ordered"
            )
        if len(timestamps) != len(set(timestamps)):
            raise ValueError(
                "methodology observation timestamps must be unique"
            )
        return validated

    @staticmethod
    def _validate_bars(
        bars: Sequence[MarketBar],
    ) -> tuple[MarketBar, ...]:
        if isinstance(bars, (str, bytes)) or not isinstance(bars, Sequence):
            raise TypeError("m5_bars must be a sequence of MarketBar")
        validated = tuple(bars)
        previous: datetime | None = None
        for bar in validated:
            if not isinstance(bar, MarketBar):
                raise TypeError("m5_bars must contain MarketBar instances")
            timestamp = bar.timestamp
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("M5 bar timestamps must be timezone-aware")
            timestamp = timestamp.astimezone(UTC)
            if previous is not None and timestamp <= previous:
                raise ValueError(
                    "M5 bar timestamps must be strictly increasing"
                )
            previous = timestamp
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
    def _validate_horizons(
        horizons: Sequence[int],
    ) -> tuple[int, ...]:
        if isinstance(horizons, (str, bytes)) or not isinstance(
            horizons,
            Sequence,
        ):
            raise TypeError("horizons must be a sequence of integers")
        validated: list[int] = []
        for horizon in horizons:
            if isinstance(horizon, bool) or not isinstance(horizon, int):
                raise TypeError("horizons must contain integers")
            if horizon <= 0:
                raise ValueError("horizons must be greater than zero")
            validated.append(horizon)
        if not validated:
            raise ValueError("horizons cannot be empty")
        if len(validated) != len(set(validated)):
            raise ValueError("horizons cannot contain duplicates")
        return tuple(sorted(validated))
