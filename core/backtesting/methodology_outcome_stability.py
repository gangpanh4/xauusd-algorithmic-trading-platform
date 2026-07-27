"""Chronological stability analytics for methodology outcome research."""

from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from core.strategies.methodology_models import (
    MethodologyDirection,
    MethodologyIdentifier,
)

from .methodology_outcome_integrity import (
    MethodologyOutcomeIntegrityAnalytics,
)
from .methodology_outcome_research import MethodologyOutcomeEvaluation


class MethodologyOutcomeStabilityAnalytics:
    """Measure confirmed-versus-baseline stability across chronological folds."""

    DEFAULT_FOLD_COUNT: Final[int] = 5

    _CSV_COLUMNS: Final[tuple[str, ...]] = (
        "Fold Number",
        "Fold Start Timestamp",
        "Fold End Timestamp",
        "Fold Observation Count",
        "Methodology",
        "Direction",
        "Horizon Bars",
        "Confirmed Sample Count",
        "Baseline Sample Count",
        "Favorable Rate Delta",
        "Average Return Delta Percent",
        "Confirmed MFE MAE Ratio",
        "Baseline MFE MAE Ratio",
        "Sample Warning",
    )

    def __init__(
        self,
        output_directory: str | Path = "output/backtests",
        *,
        fold_count: int = DEFAULT_FOLD_COUNT,
        minimum_sample_size: int = (
            MethodologyOutcomeIntegrityAnalytics.MINIMUM_SAMPLE_SIZE
        ),
    ) -> None:
        if isinstance(fold_count, bool) or not isinstance(fold_count, int):
            raise TypeError("fold_count must be an integer")
        if fold_count < 2:
            raise ValueError("fold_count must be at least two")
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.fold_count = fold_count
        self.minimum_sample_size = minimum_sample_size
        self._comparison = MethodologyOutcomeIntegrityAnalytics(
            minimum_sample_size=minimum_sample_size,
        )

    def export(
        self,
        evaluations: Sequence[MethodologyOutcomeEvaluation],
    ) -> tuple[Path, Path]:
        """Write fold-level CSV and stability-summary JSON artifacts."""

        payload, rows = self.calculate(evaluations)

        csv_path = self.output_directory / "methodology_outcome_stability.csv"
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
            self.output_directory / "methodology_outcome_stability.json"
        )
        json_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return csv_path, json_path

    def calculate(
        self,
        evaluations: Sequence[MethodologyOutcomeEvaluation],
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        """Return deterministic chronological folds and stability diagnostics."""

        validated = self._validate_evaluations(evaluations)
        timestamps = tuple(
            sorted({item.observation_timestamp.astimezone(UTC) for item in validated})
        )
        folds = self._build_folds(timestamps)

        rows: list[dict[str, object]] = []
        fold_payloads: list[dict[str, object]] = []
        for fold_number, fold_timestamps in enumerate(folds, start=1):
            timestamp_set = set(fold_timestamps)
            fold_evaluations = tuple(
                item
                for item in validated
                if item.observation_timestamp.astimezone(UTC) in timestamp_set
            )
            comparisons = self._comparison.calculate_comparisons(
                fold_evaluations
            )
            session_counts = self._dimension_counts(
                fold_evaluations,
                dimension="session",
            )
            regime_counts = self._dimension_counts(
                fold_evaluations,
                dimension="regime",
            )

            start = fold_timestamps[0] if fold_timestamps else None
            end = fold_timestamps[-1] if fold_timestamps else None
            fold_payloads.append(
                {
                    "fold_number": fold_number,
                    "start_timestamp": start.isoformat() if start else None,
                    "end_timestamp": end.isoformat() if end else None,
                    "observation_count": len(fold_timestamps),
                    "evaluation_count": len(fold_evaluations),
                    "session_counts": session_counts,
                    "regime_counts": regime_counts,
                    "comparisons": comparisons,
                }
            )

            for comparison in comparisons:
                rows.append(
                    {
                        "Fold Number": fold_number,
                        "Fold Start Timestamp": (
                            start.isoformat() if start else ""
                        ),
                        "Fold End Timestamp": end.isoformat() if end else "",
                        "Fold Observation Count": len(fold_timestamps),
                        **comparison,
                    }
                )

        stability = self._summarize_stability(rows)
        payload: dict[str, object] = {
            "fold_count": self.fold_count,
            "minimum_sample_size": self.minimum_sample_size,
            "total_unique_observations": len(timestamps),
            "total_evaluations": len(validated),
            "folds": fold_payloads,
            "stability_summary": stability,
            "observational_only": True,
            "trade_authority": False,
            "future_information_used_for_research_only": True,
        }
        return payload, rows

    def _build_folds(
        self,
        timestamps: tuple[datetime, ...],
    ) -> tuple[tuple[datetime, ...], ...]:
        if not timestamps:
            return tuple(() for _ in range(self.fold_count))

        folds: list[list[datetime]] = [
            [] for _ in range(self.fold_count)
        ]
        total = len(timestamps)
        for index, timestamp in enumerate(timestamps):
            fold_index = min(
                (index * self.fold_count) // total,
                self.fold_count - 1,
            )
            folds[fold_index].append(timestamp)
        return tuple(tuple(fold) for fold in folds)

    @staticmethod
    def _dimension_counts(
        evaluations: tuple[MethodologyOutcomeEvaluation, ...],
        *,
        dimension: str,
    ) -> dict[str, int]:
        counts: dict[str, int] = {}
        seen: set[tuple[datetime, str]] = set()
        for item in evaluations:
            if dimension == "session":
                value = item.session_name or "OFF_SESSION"
            elif dimension == "regime":
                value = item.regime_name or "MISSING"
            else:
                raise ValueError("unsupported stability dimension")
            key = (item.observation_timestamp.astimezone(UTC), value)
            if key in seen:
                continue
            seen.add(key)
            counts[value] = counts.get(value, 0) + 1
        return dict(sorted(counts.items()))

    def _summarize_stability(
        self,
        rows: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        grouped: dict[
            tuple[str, str, int],
            list[dict[str, object]],
        ] = {}
        for row in rows:
            key = (
                str(row["Methodology"]),
                str(row["Direction"]),
                int(row["Horizon Bars"]),
            )
            grouped.setdefault(key, []).append(row)

        summaries: list[dict[str, object]] = []
        for key in sorted(grouped):
            group_rows = grouped[key]
            valid_rows = [
                row
                for row in group_rows
                if not row["Sample Warning"]
                and row["Favorable Rate Delta"] is not None
                and row["Average Return Delta Percent"] is not None
            ]
            favorable_positive = sum(
                float(row["Favorable Rate Delta"]) > 0.0
                for row in valid_rows
            )
            return_positive = sum(
                float(row["Average Return Delta Percent"]) > 0.0
                for row in valid_rows
            )
            valid_count = len(valid_rows)

            warnings: list[str] = []
            if valid_count < self.fold_count:
                warnings.append("INSUFFICIENT_VALID_FOLDS")
            if valid_count:
                if favorable_positive not in {0, valid_count}:
                    warnings.append("FAVORABLE_RATE_SIGN_UNSTABLE")
                if return_positive not in {0, valid_count}:
                    warnings.append("RETURN_SIGN_UNSTABLE")
            else:
                warnings.append("NO_VALID_FOLDS")

            summaries.append(
                {
                    "methodology": key[0],
                    "direction": key[1],
                    "horizon_bars": key[2],
                    "valid_fold_count": valid_count,
                    "positive_favorable_delta_folds": favorable_positive,
                    "positive_return_delta_folds": return_positive,
                    "average_favorable_rate_delta": self._average(
                        valid_rows,
                        "Favorable Rate Delta",
                    ),
                    "average_return_delta_percent": self._average(
                        valid_rows,
                        "Average Return Delta Percent",
                    ),
                    "warnings": warnings,
                }
            )
        return summaries

    @staticmethod
    def _average(
        rows: list[dict[str, object]],
        field: str,
    ) -> float | None:
        if not rows:
            return None
        return sum(float(row[field]) for row in rows) / len(rows)

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
