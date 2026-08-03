"""Strict-exact probability-rejected subset research for Variant B."""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import mean, median
from typing import Final

from core.trading_pipeline.models import (
    PipelineObservationAudit,
    PipelineStage,
)

from .methodology_observer import MethodologyObservation
from .methodology_variant_b_atr_shadow_matrix import (
    MethodologyVariantBATRShadowMatrix,
    VariantBATRShadowResult,
)


class MethodologyVariantBProbabilitySubset:
    """Analyze exact Variant B rows rejected by the probability gate."""

    VARIANT: Final[str] = (
        "VARIANT_B_BEARISH_EXCLUDE_COMPATIBLE_SWEEP"
    )
    STOP_ATR_MULTIPLE: Final[float] = 1.0
    TARGET_R: Final[float] = 2.0
    BOOTSTRAP_SAMPLES: Final[int] = 2_000
    BOOTSTRAP_SEED: Final[int] = 20260803
    PROBABILITY_BANDS: Final[tuple[tuple[float, float], ...]] = (
        (0.0, 0.1),
        (0.1, 0.2),
        (0.2, 0.3),
        (0.3, 0.4),
        (0.4, 0.5),
        (0.5, 0.6),
        (0.6, 0.7),
        (0.7, 0.8),
        (0.8, 0.9),
        (0.9, 1.0000000001),
    )
    ROUND_TRIP_COST_PRICE_UNITS: Final[
        tuple[tuple[str, float], ...]
    ] = (
        ("ZERO_COST", 0.00),
        ("LOW_COST", 0.10),
        ("MEDIUM_COST", 0.25),
        ("HIGH_COST", 0.50),
    )

    _CSV_COLUMNS: Final[tuple[str, ...]] = (
        "Variant",
        "Probability Band",
        "Probability Band Lower",
        "Probability Band Upper",
        "Cost Scenario",
        "Round Trip Cost Price Units",
        "Trade Count",
        "Average Net R",
        "Median Net R",
        "Total Net R",
        "Profit Factor Net R",
        "Positive Trade Rate",
        "Maximum Drawdown Net R",
        "Bootstrap CI 95 Lower",
        "Bootstrap CI 95 Upper",
        "Bootstrap Probability Mean Above Zero",
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
            / "methodology_variant_b_probability_subset.csv"
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
            / "methodology_variant_b_probability_subset.json"
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
        audit_by_timestamp = {
            audit.timestamp: audit
            for audit in audits
        }

        _, matrix_results = self.matrix.calculate(
            observations,
            m5_bars,
            window_metadata=window_metadata,
        )
        scenario_results = tuple(
            result
            for result in matrix_results
            if result.stop_atr_multiple == self.STOP_ATR_MULTIPLE
            and result.target_r == self.TARGET_R
        )

        subset: list[
            tuple[VariantBATRShadowResult, PipelineObservationAudit]
        ] = []
        excluded_missing_probability = 0
        for result in scenario_results:
            audit = audit_by_timestamp.get(
                result.observation_timestamp
            )
            if audit is None:
                continue
            if audit.rejection_stage is not PipelineStage.PROBABILITY:
                continue
            if audit.reason_code != "PROBABILITY_REJECTED":
                continue
            if audit.probability_value is None:
                excluded_missing_probability += 1
                continue
            subset.append((result, audit))

        band_members: dict[
            str,
            list[tuple[VariantBATRShadowResult, PipelineObservationAudit]],
        ] = defaultdict(list)
        for result, audit in subset:
            label = self._band_label(audit.probability_value)
            band_members[label].append((result, audit))

        rows: list[dict[str, object]] = []
        band_payloads: list[dict[str, object]] = []
        for lower, upper in self.PROBABILITY_BANDS:
            label = self._format_band(lower, upper)
            members = band_members.get(label, [])
            band_payload = {
                "probability_band": label,
                "lower_inclusive": lower,
                "upper_exclusive": (
                    1.0 if upper > 1.0 else upper
                ),
                "trade_count": len(members),
                "cost_scenarios": [],
            }

            for cost_name, cost_price_units in (
                self.ROUND_TRIP_COST_PRICE_UNITS
            ):
                net_values = [
                    result.result_r
                    - (
                        cost_price_units
                        / (
                            result.atr_14
                            * self.STOP_ATR_MULTIPLE
                        )
                    )
                    for result, _ in members
                ]
                bootstrap = self._bootstrap(net_values)
                summary = self._summary(net_values)
                band_payload["cost_scenarios"].append(
                    {
                        "name": cost_name,
                        "round_trip_cost_price_units": (
                            cost_price_units
                        ),
                        **summary,
                        "bootstrap": bootstrap,
                    }
                )
                rows.append(
                    {
                        "Variant": self.VARIANT,
                        "Probability Band": label,
                        "Probability Band Lower": lower,
                        "Probability Band Upper": (
                            1.0 if upper > 1.0 else upper
                        ),
                        "Cost Scenario": cost_name,
                        "Round Trip Cost Price Units": (
                            cost_price_units
                        ),
                        "Trade Count": summary["trade_count"],
                        "Average Net R": summary["average_r"],
                        "Median Net R": summary["median_r"],
                        "Total Net R": summary["total_r"],
                        "Profit Factor Net R": (
                            summary["profit_factor_r"]
                        ),
                        "Positive Trade Rate": (
                            summary["positive_trade_rate"]
                        ),
                        "Maximum Drawdown Net R": (
                            summary["maximum_drawdown_r"]
                        ),
                        "Bootstrap CI 95 Lower": (
                            bootstrap["confidence_interval_95"][0]
                        ),
                        "Bootstrap CI 95 Upper": (
                            bootstrap["confidence_interval_95"][1]
                        ),
                        "Bootstrap Probability Mean Above Zero": (
                            bootstrap[
                                "probability_average_r_above_zero"
                            ]
                        ),
                    }
                )
            band_payloads.append(band_payload)

        zero_cost_values = [
            result.result_r for result, _ in subset
        ]
        probability_values = [
            audit.probability_value
            for _, audit in subset
            if audit.probability_value is not None
        ]
        monthly = self._monthly(subset)
        best_five_removed = self._remove_best_five_percent(
            zero_cost_values
        )

        payload = {
            "variant": self.VARIANT,
            "subset_definition": {
                "alignment": "STRICT_EXACT_TIMESTAMP_ONLY",
                "active_rejection_stage": "PROBABILITY",
                "active_reason_code": "PROBABILITY_REJECTED",
                "probability_value_required": True,
                "stop_atr_multiple": self.STOP_ATR_MULTIPLE,
                "target_r": self.TARGET_R,
            },
            "subset_counts": {
                "scenario_shadow_trade_count": len(
                    scenario_results
                ),
                "strict_exact_probability_rejected_count": len(
                    subset
                ),
                "excluded_missing_probability_value_count": (
                    excluded_missing_probability
                ),
            },
            "probability_distribution": {
                "minimum": min(probability_values)
                if probability_values
                else None,
                "maximum": max(probability_values)
                if probability_values
                else None,
                "average": mean(probability_values)
                if probability_values
                else None,
                "median": median(probability_values)
                if probability_values
                else None,
            },
            "overall_zero_cost": {
                **self._summary(zero_cost_values),
                "bootstrap": self._bootstrap(zero_cost_values),
            },
            "probability_bands": band_payloads,
            "monthly_stability": {
                "month_count": len(monthly),
                "positive_month_count": sum(
                    sum(values) > 0.0
                    for values in monthly.values()
                ),
                "negative_month_count": sum(
                    sum(values) < 0.0
                    for values in monthly.values()
                ),
                "months": {
                    month: self._summary(values)
                    for month, values in sorted(monthly.items())
                },
            },
            "best_5_percent_concentration": best_five_removed,
            "cost_definition": (
                "Adverse total round-trip price cost converted to R "
                "using each trade's pre-entry ATR stop distance."
            ),
            "window_metadata": dict(window_metadata or {}),
            "decision_rule": {
                "probability_threshold_change_approved": False,
                "required_next_evidence": (
                    "Independent July replication of the same strict "
                    "exact subset and unchanged probability bands."
                ),
            },
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

    def _band_label(self, value: float) -> str:
        for lower, upper in self.PROBABILITY_BANDS:
            if lower <= value < upper:
                return self._format_band(lower, upper)
        raise ValueError("probability value is outside [0, 1]")

    @staticmethod
    def _format_band(lower: float, upper: float) -> str:
        bounded_upper = 1.0 if upper > 1.0 else upper
        return f"[{lower:.1f},{bounded_upper:.1f})"

    def _bootstrap(
        self,
        values: Sequence[float],
    ) -> dict[str, object]:
        if not values:
            return {
                "sample_count": 0,
                "bootstrap_samples": self.BOOTSTRAP_SAMPLES,
                "seed": self.BOOTSTRAP_SEED,
                "confidence_interval_95": [None, None],
                "probability_average_r_above_zero": None,
            }

        rng = random.Random(self.BOOTSTRAP_SEED)
        estimates = sorted(
            mean(
                rng.choice(values)
                for _ in range(len(values))
            )
            for _ in range(self.BOOTSTRAP_SAMPLES)
        )
        lower_index = int(0.025 * (len(estimates) - 1))
        upper_index = int(0.975 * (len(estimates) - 1))
        return {
            "sample_count": len(values),
            "bootstrap_samples": self.BOOTSTRAP_SAMPLES,
            "seed": self.BOOTSTRAP_SEED,
            "confidence_interval_95": [
                estimates[lower_index],
                estimates[upper_index],
            ],
            "probability_average_r_above_zero": (
                sum(value > 0.0 for value in estimates)
                / len(estimates)
            ),
        }

    def _monthly(
        self,
        subset: Sequence[
            tuple[VariantBATRShadowResult, PipelineObservationAudit]
        ],
    ) -> dict[str, list[float]]:
        groups: dict[str, list[float]] = defaultdict(list)
        for result, _ in subset:
            groups[
                result.entry_timestamp.strftime("%Y-%m")
            ].append(result.result_r)
        return dict(groups)

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
                "remaining_profit_factor_r": None,
            }

        remove_count = max(1, int(len(values) * 0.05))
        ordered = sorted(values, reverse=True)
        remaining = ordered[remove_count:]
        summary = self._summary(remaining)
        return {
            "removed_trade_count": remove_count,
            "removed_total_r": sum(ordered[:remove_count]),
            "remaining_trade_count": summary["trade_count"],
            "remaining_average_r": summary["average_r"],
            "remaining_total_r": summary["total_r"],
            "remaining_profit_factor_r": (
                summary["profit_factor_r"]
            ),
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
                sum(value > 0.0 for value in values)
                / len(values)
                if values
                else None
            ),
            "maximum_drawdown_r": self._maximum_drawdown(
                values
            ),
        }

    @staticmethod
    def _profit_factor(
        values: Sequence[float],
    ) -> float | None:
        gains = sum(value for value in values if value > 0.0)
        losses = -sum(value for value in values if value < 0.0)
        return gains / losses if losses > 0.0 else None

    @staticmethod
    def _maximum_drawdown(
        values: Sequence[float],
    ) -> float:
        equity = 0.0
        peak = 0.0
        maximum = 0.0
        for value in values:
            equity += value
            peak = max(peak, equity)
            maximum = max(maximum, peak - equity)
        return maximum
