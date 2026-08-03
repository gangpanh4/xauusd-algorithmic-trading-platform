"""Observational monitor for the frozen Variant B shadow exception cohort."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

from core.trading_pipeline.models import PipelineObservationAudit

from .methodology_observer import MethodologyObservation
from .methodology_variant_b_probability_subset import (
    MethodologyVariantBProbabilitySubset,
)


class MethodologyVariantBShadowExceptionMonitor:
    """Track the frozen probability-rejected cohort without trading authority."""

    VARIANT: Final[str] = (
        "VARIANT_B_BEARISH_EXCLUDE_COMPATIBLE_SWEEP"
    )
    PROBABILITY_LOWER: Final[float] = 0.5
    PROBABILITY_UPPER: Final[float] = 0.6
    PROBABILITY_BAND: Final[str] = "[0.5,0.6)"
    STOP_ATR_MULTIPLE: Final[float] = 1.0
    TARGET_R: Final[float] = 2.0

    _CSV_COLUMNS: Final[tuple[str, ...]] = (
        "Monitor Sequence",
        "Variant",
        "Observation Timestamp",
        "Entry Timestamp",
        "Exit Timestamp",
        "Probability Value",
        "Probability Band",
        "Gross Result R",
        "Net R Zero Cost",
        "Net R Low Cost",
        "Net R Medium Cost",
        "Net R High Cost",
        "Cumulative Gross R",
        "Cumulative Net R Low Cost",
        "Cumulative Net R Medium Cost",
        "Cumulative Net R High Cost",
        "Gross Equity Peak R",
        "Gross Drawdown R",
        "Maximum Gross Drawdown To Date R",
        "Exit Reason",
        "Holding Bars",
        "Session",
        "Regime",
        "Requested End Time",
        "M5 Window First Timestamp",
        "M5 Window Last Timestamp",
    )

    def __init__(
        self,
        output_directory: str | Path = "output/backtests",
    ) -> None:
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.probability_subset = MethodologyVariantBProbabilitySubset(
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
            / "methodology_variant_b_shadow_exception_monitor.csv"
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
            / "methodology_variant_b_shadow_exception_monitor.json"
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
        subset_payload, _ = self.probability_subset.calculate(
            observations,
            audits,
            m5_bars,
            window_metadata=window_metadata,
        )
        details = tuple(
            row
            for row in subset_payload["trade_details"]
            if row["Probability Band"] == self.PROBABILITY_BAND
            and self.PROBABILITY_LOWER
            <= float(row["Probability Value"])
            < self.PROBABILITY_UPPER
        )

        rows = self._monitor_rows(details)
        gross_values = [
            float(row["Gross Result R"])
            for row in rows
        ]
        low_cost_values = [
            float(row["Net R Low Cost"])
            for row in rows
        ]
        medium_cost_values = [
            float(row["Net R Medium Cost"])
            for row in rows
        ]
        high_cost_values = [
            float(row["Net R High Cost"])
            for row in rows
        ]

        payload = {
            "variant": self.VARIANT,
            "monitor_definition": {
                "alignment": "STRICT_EXACT_TIMESTAMP_ONLY",
                "active_rejection_stage": "PROBABILITY",
                "active_reason_code": "PROBABILITY_REJECTED",
                "probability_lower_inclusive": self.PROBABILITY_LOWER,
                "probability_upper_exclusive": self.PROBABILITY_UPPER,
                "probability_band": self.PROBABILITY_BAND,
                "entry_policy": "FIRST_AVAILABLE_WHILE_FLAT",
                "stop_atr_multiple": self.STOP_ATR_MULTIPLE,
                "target_r": self.TARGET_R,
                "maximum_holding_bars": 24,
                "same_candle_policy": "CONSERVATIVE_STOP_FIRST",
            },
            "counts": {
                "monitored_trade_count": len(rows),
                "winning_trade_count": sum(
                    value > 0.0 for value in gross_values
                ),
                "losing_trade_count": sum(
                    value < 0.0 for value in gross_values
                ),
                "flat_trade_count": sum(
                    value == 0.0 for value in gross_values
                ),
            },
            "gross_performance": self._summary(gross_values),
            "cost_performance": {
                "LOW_COST": self._summary(low_cost_values),
                "MEDIUM_COST": self._summary(medium_cost_values),
                "HIGH_COST": self._summary(high_cost_values),
            },
            "latest_state": (
                {
                    "last_observation_timestamp": rows[-1][
                        "Observation Timestamp"
                    ],
                    "cumulative_gross_r": rows[-1][
                        "Cumulative Gross R"
                    ],
                    "maximum_gross_drawdown_r": rows[-1][
                        "Maximum Gross Drawdown To Date R"
                    ],
                }
                if rows
                else {
                    "last_observation_timestamp": None,
                    "cumulative_gross_r": 0.0,
                    "maximum_gross_drawdown_r": 0.0,
                }
            ),
            "window_metadata": dict(window_metadata or {}),
            "observational_only": True,
            "trade_authority": False,
            "signal_authority": False,
            "approval_authority": False,
            "position_sizing_authority": False,
            "order_creation_authority": False,
            "active_decision_modified": False,
            "active_pipeline_modified": False,
            "probability_threshold_modified": False,
            "shadow_exception_approved": False,
            "future_information_used_for_research_only": True,
        }
        return payload, rows

    def _monitor_rows(
        self,
        details: Sequence[Mapping[str, object]],
    ) -> list[dict[str, object]]:
        cumulative_gross = 0.0
        cumulative_low = 0.0
        cumulative_medium = 0.0
        cumulative_high = 0.0
        gross_peak = 0.0
        maximum_drawdown = 0.0
        rows: list[dict[str, object]] = []

        for sequence, detail in enumerate(
            sorted(
                details,
                key=lambda row: str(row["Observation Timestamp"]),
            ),
            start=1,
        ):
            gross = float(detail["Gross Result R"])
            low = float(detail["Net R Low Cost"])
            medium = float(detail["Net R Medium Cost"])
            high = float(detail["Net R High Cost"])
            cumulative_gross += gross
            cumulative_low += low
            cumulative_medium += medium
            cumulative_high += high
            gross_peak = max(gross_peak, cumulative_gross)
            drawdown = gross_peak - cumulative_gross
            maximum_drawdown = max(maximum_drawdown, drawdown)

            rows.append(
                {
                    "Monitor Sequence": sequence,
                    "Variant": detail["Variant"],
                    "Observation Timestamp": detail[
                        "Observation Timestamp"
                    ],
                    "Entry Timestamp": detail["Entry Timestamp"],
                    "Exit Timestamp": detail["Exit Timestamp"],
                    "Probability Value": detail["Probability Value"],
                    "Probability Band": detail["Probability Band"],
                    "Gross Result R": gross,
                    "Net R Zero Cost": detail["Net R Zero Cost"],
                    "Net R Low Cost": low,
                    "Net R Medium Cost": medium,
                    "Net R High Cost": high,
                    "Cumulative Gross R": cumulative_gross,
                    "Cumulative Net R Low Cost": cumulative_low,
                    "Cumulative Net R Medium Cost": cumulative_medium,
                    "Cumulative Net R High Cost": cumulative_high,
                    "Gross Equity Peak R": gross_peak,
                    "Gross Drawdown R": drawdown,
                    "Maximum Gross Drawdown To Date R": (
                        maximum_drawdown
                    ),
                    "Exit Reason": detail["Exit Reason"],
                    "Holding Bars": detail["Holding Bars"],
                    "Session": detail["Session"],
                    "Regime": detail["Regime"],
                    "Requested End Time": detail[
                        "Requested End Time"
                    ],
                    "M5 Window First Timestamp": detail[
                        "M5 Window First Timestamp"
                    ],
                    "M5 Window Last Timestamp": detail[
                        "M5 Window Last Timestamp"
                    ],
                }
            )
        return rows

    @staticmethod
    def _summary(values: Sequence[float]) -> dict[str, object]:
        if not values:
            return {
                "trade_count": 0,
                "average_r": None,
                "total_r": 0.0,
                "profit_factor_r": None,
                "positive_trade_rate": None,
                "maximum_drawdown_r": 0.0,
            }

        gains = sum(value for value in values if value > 0.0)
        losses = -sum(value for value in values if value < 0.0)
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

        return {
            "trade_count": len(values),
            "average_r": sum(values) / len(values),
            "total_r": sum(values),
            "profit_factor_r": (
                gains / losses if losses > 0.0 else None
            ),
            "positive_trade_rate": (
                sum(value > 0.0 for value in values)
                / len(values)
            ),
            "maximum_drawdown_r": maximum_drawdown,
        }
