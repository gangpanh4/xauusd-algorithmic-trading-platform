"""Statistical stability research for frozen Variant B baseline."""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from typing import Final

from .methodology_observer import MethodologyObservation
from .methodology_variant_b_atr_shadow_matrix import (
    MethodologyVariantBATRShadowMatrix,
    VariantBATRShadowResult,
)


class MethodologyVariantBStatisticalStability:
    """Assess concentration and sampling stability without trade authority."""

    VARIANT: Final[str] = (
        "VARIANT_B_BEARISH_EXCLUDE_COMPATIBLE_SWEEP"
    )
    STOP_ATR_MULTIPLE: Final[float] = 1.0
    TARGET_R: Final[float] = 2.0
    ROLLING_BLOCK_SIZE: Final[int] = 50
    BOOTSTRAP_SAMPLES: Final[int] = 2_000
    BOOTSTRAP_SEED: Final[int] = 20260803

    _CSV_COLUMNS: Final[tuple[str, ...]] = (
        "Variant",
        "Section",
        "Group",
        "Trade Count",
        "Average R",
        "Median R",
        "Total R",
        "Profit Factor R",
        "Positive Trade Rate",
        "Maximum Drawdown R",
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
        m5_bars: Sequence[object],
        *,
        window_metadata: Mapping[str, object] | None = None,
    ) -> tuple[Path, Path]:
        payload, rows = self.calculate(
            observations,
            m5_bars,
            window_metadata=window_metadata,
        )

        csv_path = (
            self.output_directory
            / "methodology_variant_b_statistical_stability.csv"
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
            / "methodology_variant_b_statistical_stability.json"
        )
        json_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return csv_path, json_path

    def calculate(
        self,
        observations: Sequence[MethodologyObservation],
        m5_bars: Sequence[object],
        *,
        window_metadata: Mapping[str, object] | None = None,
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        _, matrix_results = self.matrix.calculate(
            observations,
            m5_bars,
            window_metadata=window_metadata,
        )
        results = tuple(
            item
            for item in matrix_results
            if item.stop_atr_multiple == self.STOP_ATR_MULTIPLE
            and item.target_r == self.TARGET_R
        )
        values = [item.result_r for item in results]

        monthly = self._monthly(results)
        rolling = self._rolling_blocks(results)
        overall = self._summary(values)

        longest_losing_streak = self._longest_losing_streak(values)
        drawdown_duration = self._maximum_drawdown_duration(values)
        bootstrap = self._bootstrap_average_r(values)
        best_month_removed = self._remove_best_month(monthly)
        best_five_percent_removed = self._remove_best_five_percent(values)

        rows: list[dict[str, object]] = []
        for month_name, month_values in sorted(monthly.items()):
            rows.append(
                self._row(
                    section="MONTH",
                    group=month_name,
                    values=month_values,
                )
            )
        for index, block_values in enumerate(rolling, start=1):
            rows.append(
                self._row(
                    section="ROLLING_50_TRADES",
                    group=f"BLOCK_{index:03d}",
                    values=block_values,
                )
            )

        payload = {
            "variant": self.VARIANT,
            "frozen_scenario": {
                "stop_atr_multiple": self.STOP_ATR_MULTIPLE,
                "target_r": self.TARGET_R,
                "entry_policy": "FIRST_AVAILABLE_WHILE_FLAT",
                "horizon_bars": self.matrix.HORIZON_BARS,
            },
            "trade_count": len(results),
            "overall": overall,
            "monthly_summary": {
                "month_count": len(monthly),
                "positive_month_count": sum(
                    sum(month_values) > 0.0
                    for month_values in monthly.values()
                ),
                "negative_month_count": sum(
                    sum(month_values) < 0.0
                    for month_values in monthly.values()
                ),
                "flat_month_count": sum(
                    sum(month_values) == 0.0
                    for month_values in monthly.values()
                ),
                "months": {
                    month: self._summary(month_values)
                    for month, month_values in sorted(monthly.items())
                },
            },
            "rolling_trade_blocks": {
                "block_size": self.ROLLING_BLOCK_SIZE,
                "block_count": len(rolling),
                "positive_block_count": sum(
                    sum(block) > 0.0 for block in rolling
                ),
                "negative_block_count": sum(
                    sum(block) < 0.0 for block in rolling
                ),
                "blocks": [
                    {
                        "block": index,
                        **self._summary(block),
                    }
                    for index, block in enumerate(rolling, start=1)
                ],
            },
            "longest_losing_streak_trades": longest_losing_streak,
            "maximum_drawdown_duration_trades": drawdown_duration,
            "bootstrap_average_r": bootstrap,
            "concentration_sensitivity": {
                "remove_best_month": best_month_removed,
                "remove_best_5_percent_of_trades": (
                    best_five_percent_removed
                ),
            },
            "methodology_notes": {
                "bootstrap": (
                    "Deterministic trade-level resampling with replacement "
                    "using a fixed seed."
                ),
                "rolling_blocks": (
                    "Non-overlapping chronological blocks of 50 executed "
                    "shadow trades; final partial block is retained."
                ),
                "drawdown_duration": (
                    "Maximum number of consecutive trades spent below the "
                    "previous equity peak."
                ),
            },
            "window_metadata": dict(window_metadata or {}),
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

    def _monthly(
        self,
        results: Sequence[VariantBATRShadowResult],
    ) -> dict[str, list[float]]:
        groups: dict[str, list[float]] = defaultdict(list)
        for result in results:
            timestamp = result.entry_timestamp
            if not isinstance(timestamp, datetime):
                continue
            groups[timestamp.strftime("%Y-%m")].append(result.result_r)
        return dict(groups)

    def _rolling_blocks(
        self,
        results: Sequence[VariantBATRShadowResult],
    ) -> list[list[float]]:
        ordered = sorted(results, key=lambda item: item.entry_timestamp)
        values = [item.result_r for item in ordered]
        return [
            values[index : index + self.ROLLING_BLOCK_SIZE]
            for index in range(0, len(values), self.ROLLING_BLOCK_SIZE)
        ]

    def _bootstrap_average_r(
        self,
        values: Sequence[float],
    ) -> dict[str, object]:
        if not values:
            return {
                "sample_count": 0,
                "bootstrap_samples": self.BOOTSTRAP_SAMPLES,
                "mean_average_r": None,
                "confidence_interval_95": [None, None],
                "probability_average_r_above_zero": None,
            }

        rng = random.Random(self.BOOTSTRAP_SEED)
        sample_size = len(values)
        estimates = sorted(
            mean(rng.choice(values) for _ in range(sample_size))
            for _ in range(self.BOOTSTRAP_SAMPLES)
        )
        lower_index = int(0.025 * (self.BOOTSTRAP_SAMPLES - 1))
        upper_index = int(0.975 * (self.BOOTSTRAP_SAMPLES - 1))
        return {
            "sample_count": sample_size,
            "bootstrap_samples": self.BOOTSTRAP_SAMPLES,
            "seed": self.BOOTSTRAP_SEED,
            "mean_average_r": mean(estimates),
            "confidence_interval_95": [
                estimates[lower_index],
                estimates[upper_index],
            ],
            "probability_average_r_above_zero": (
                sum(value > 0.0 for value in estimates)
                / len(estimates)
            ),
        }

    def _remove_best_month(
        self,
        monthly: Mapping[str, Sequence[float]],
    ) -> dict[str, object]:
        if not monthly:
            return {
                "removed_month": None,
                "remaining_trade_count": 0,
                "remaining_average_r": None,
                "remaining_total_r": 0.0,
            }

        removed_month = max(
            monthly,
            key=lambda month: sum(monthly[month]),
        )
        remaining = [
            value
            for month, month_values in monthly.items()
            if month != removed_month
            for value in month_values
        ]
        return {
            "removed_month": removed_month,
            "removed_month_total_r": sum(monthly[removed_month]),
            "remaining_trade_count": len(remaining),
            "remaining_average_r": (
                mean(remaining) if remaining else None
            ),
            "remaining_total_r": sum(remaining),
            "remaining_profit_factor_r": self._profit_factor(remaining),
        }

    def _remove_best_five_percent(
        self,
        values: Sequence[float],
    ) -> dict[str, object]:
        if not values:
            return {
                "removed_trade_count": 0,
                "remaining_trade_count": 0,
                "remaining_average_r": None,
                "remaining_total_r": 0.0,
            }

        remove_count = max(1, int(len(values) * 0.05))
        ordered = sorted(values, reverse=True)
        removed = ordered[:remove_count]
        remaining = ordered[remove_count:]
        return {
            "removed_trade_count": remove_count,
            "removed_total_r": sum(removed),
            "remaining_trade_count": len(remaining),
            "remaining_average_r": (
                mean(remaining) if remaining else None
            ),
            "remaining_total_r": sum(remaining),
            "remaining_profit_factor_r": self._profit_factor(remaining),
        }

    @staticmethod
    def _longest_losing_streak(values: Sequence[float]) -> int:
        longest = 0
        current = 0
        for value in values:
            if value < 0.0:
                current += 1
                longest = max(longest, current)
            else:
                current = 0
        return longest

    @staticmethod
    def _maximum_drawdown_duration(values: Sequence[float]) -> int:
        equity = 0.0
        peak = 0.0
        current_duration = 0
        maximum_duration = 0
        for value in values:
            equity += value
            if equity >= peak:
                peak = equity
                current_duration = 0
            else:
                current_duration += 1
                maximum_duration = max(
                    maximum_duration,
                    current_duration,
                )
        return maximum_duration

    def _row(
        self,
        *,
        section: str,
        group: str,
        values: Sequence[float],
    ) -> dict[str, object]:
        summary = self._summary(values)
        return {
            "Variant": self.VARIANT,
            "Section": section,
            "Group": group,
            "Trade Count": summary["trade_count"],
            "Average R": summary["average_r"],
            "Median R": summary["median_r"],
            "Total R": summary["total_r"],
            "Profit Factor R": summary["profit_factor_r"],
            "Positive Trade Rate": summary["positive_trade_rate"],
            "Maximum Drawdown R": summary["maximum_drawdown_r"],
        }

    def _summary(
        self,
        values: Sequence[float],
    ) -> dict[str, object]:
        return {
            "trade_count": len(values),
            "average_r": mean(values) if values else None,
            "median_r": median(values) if values else None,
            "total_r": sum(values),
            "profit_factor_r": self._profit_factor(values),
            "positive_trade_rate": (
                sum(value > 0.0 for value in values) / len(values)
                if values
                else None
            ),
            "maximum_drawdown_r": self._maximum_drawdown(values),
        }

    @staticmethod
    def _profit_factor(values: Sequence[float]) -> float | None:
        gains = sum(value for value in values if value > 0.0)
        losses = -sum(value for value in values if value < 0.0)
        return gains / losses if losses > 0.0 else None

    @staticmethod
    def _maximum_drawdown(values: Sequence[float]) -> float:
        equity = 0.0
        peak = 0.0
        maximum_drawdown = 0.0
        for value in values:
            equity += value
            peak = max(peak, equity)
            maximum_drawdown = max(
                maximum_drawdown,
                peak - equity,
            )
        return maximum_drawdown
