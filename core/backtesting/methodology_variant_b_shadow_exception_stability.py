"""Stability analytics for the frozen Variant B shadow-exception cohort."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Final

from core.trading_pipeline.models import PipelineObservationAudit
from .methodology_observer import MethodologyObservation
from .methodology_variant_b_shadow_exception_monitor import (
    MethodologyVariantBShadowExceptionMonitor,
)


class MethodologyVariantBShadowExceptionStability:
    """Report chronological deterioration without trading authority."""

    ROLLING_WINDOW_TRADES: Final[int] = 10
    REFERENCE_AVERAGE_R: Final[float] = 0.26890733462685417
    REFERENCE_PROFIT_FACTOR: Final[float] = 1.475069596922715
    REFERENCE_MAXIMUM_DRAWDOWN_R: Final[float] = 11.747911264765278
    REFERENCE_HIGH_COST_AVERAGE_R: Final[float] = 0.17822340192839045

    _CSV_COLUMNS: Final[tuple[str, ...]] = (
        "Window Type", "Window Label", "First Observation Timestamp",
        "Last Observation Timestamp", "Trade Count", "Average Gross R",
        "Total Gross R", "Gross Profit Factor", "Gross Positive Trade Rate",
        "Maximum Gross Drawdown R", "Longest Gross Drawdown Duration Trades",
        "Maximum Consecutive Losses", "Average High Cost R",
        "Total High Cost R", "High Cost Profit Factor",
        "Average R Versus Reference", "Profit Factor Versus Reference",
        "Maximum Drawdown Versus Reference", "Deterioration Flag",
    )

    def __init__(self, output_directory: str | Path = "output/backtests") -> None:
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.monitor = MethodologyVariantBShadowExceptionMonitor(output_directory)

    def export(
        self,
        observations: Sequence[MethodologyObservation],
        audits: Sequence[PipelineObservationAudit],
        m5_bars: Sequence[object],
        *,
        window_metadata: Mapping[str, object] | None = None,
    ) -> tuple[Path, Path]:
        payload, rows = self.calculate(
            observations, audits, m5_bars, window_metadata=window_metadata
        )
        csv_path = self.output_directory / (
            "methodology_variant_b_shadow_exception_stability.csv"
        )
        with csv_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(self._CSV_COLUMNS))
            writer.writeheader()
            writer.writerows(rows)
        json_path = self.output_directory / (
            "methodology_variant_b_shadow_exception_stability.json"
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
        monitor_payload, monitor_rows = self.monitor.calculate(
            observations, audits, m5_bars, window_metadata=window_metadata
        )
        rows = sorted(
            monitor_rows, key=lambda row: str(row["Observation Timestamp"])
        )
        rolling = self._rolling_rows(rows)
        monthly = self._calendar_rows(rows, "MONTH")
        quarterly = self._calendar_rows(rows, "QUARTER")
        gross = [float(row["Gross Result R"]) for row in rows]
        high = [float(row["Net R High Cost"]) for row in rows]
        overall = self._summary(gross, high)
        payload = {
            "variant": monitor_payload["variant"],
            "stability_definition": {
                "cohort": monitor_payload["monitor_definition"],
                "rolling_window_trades": self.ROLLING_WINDOW_TRADES,
                "reference_source": (
                    "Frozen combined April-July strict-exact [0.5,0.6) validation."
                ),
                "reference_metrics": {
                    "average_r": self.REFERENCE_AVERAGE_R,
                    "profit_factor_r": self.REFERENCE_PROFIT_FACTOR,
                    "maximum_drawdown_r": self.REFERENCE_MAXIMUM_DRAWDOWN_R,
                    "high_cost_average_r": self.REFERENCE_HIGH_COST_AVERAGE_R,
                },
            },
            "overall": {
                **overall,
                "deterioration_flags": self._deterioration_flags(overall),
            },
            "rolling_windows": [self._payload_row(row) for row in rolling],
            "monthly_stability": [self._payload_row(row) for row in monthly],
            "quarterly_stability": [self._payload_row(row) for row in quarterly],
            "latest_window": self._payload_row(rolling[-1]) if rolling else None,
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
        return payload, rolling + monthly + quarterly

    def _rolling_rows(
        self, rows: Sequence[Mapping[str, object]]
    ) -> list[dict[str, object]]:
        output = []
        for end in range(len(rows)):
            window = rows[max(0, end - self.ROLLING_WINDOW_TRADES + 1): end + 1]
            output.append(self._report_row("ROLLING", f"ENDING_{window[-1]['Observation Timestamp']}", window))
        return output

    def _calendar_rows(
        self, rows: Sequence[Mapping[str, object]], period: str
    ) -> list[dict[str, object]]:
        groups: dict[str, list[Mapping[str, object]]] = defaultdict(list)
        for row in rows:
            timestamp = datetime.fromisoformat(str(row["Observation Timestamp"]))
            if period == "MONTH":
                label = timestamp.strftime("%Y-%m")
            elif period == "QUARTER":
                label = f"{timestamp.year}-Q{((timestamp.month - 1) // 3) + 1}"
            else:
                raise ValueError(f"unsupported period: {period}")
            groups[label].append(row)
        return [
            self._report_row(period, label, group)
            for label, group in sorted(groups.items())
        ]

    def _report_row(
        self, window_type: str, label: str,
        rows: Sequence[Mapping[str, object]]
    ) -> dict[str, object]:
        gross = [float(row["Gross Result R"]) for row in rows]
        high = [float(row["Net R High Cost"]) for row in rows]
        summary = self._summary(gross, high)
        flags = self._deterioration_flags(summary)
        pf = summary["gross_profit_factor"]
        return {
            "Window Type": window_type,
            "Window Label": label,
            "First Observation Timestamp": rows[0]["Observation Timestamp"],
            "Last Observation Timestamp": rows[-1]["Observation Timestamp"],
            "Trade Count": summary["trade_count"],
            "Average Gross R": summary["average_gross_r"],
            "Total Gross R": summary["total_gross_r"],
            "Gross Profit Factor": pf,
            "Gross Positive Trade Rate": summary["gross_positive_trade_rate"],
            "Maximum Gross Drawdown R": summary["maximum_gross_drawdown_r"],
            "Longest Gross Drawdown Duration Trades": summary[
                "longest_gross_drawdown_duration_trades"
            ],
            "Maximum Consecutive Losses": summary["maximum_consecutive_losses"],
            "Average High Cost R": summary["average_high_cost_r"],
            "Total High Cost R": summary["total_high_cost_r"],
            "High Cost Profit Factor": summary["high_cost_profit_factor"],
            "Average R Versus Reference": (
                summary["average_gross_r"] - self.REFERENCE_AVERAGE_R
            ),
            "Profit Factor Versus Reference": (
                pf - self.REFERENCE_PROFIT_FACTOR if pf is not None else None
            ),
            "Maximum Drawdown Versus Reference": (
                summary["maximum_gross_drawdown_r"]
                - self.REFERENCE_MAXIMUM_DRAWDOWN_R
            ),
            "Deterioration Flag": "|".join(flags) if flags else "NONE",
        }

    def _summary(
        self, gross_values: Sequence[float], high_values: Sequence[float]
    ) -> dict[str, object]:
        gross = self._series_summary(gross_values)
        high = self._series_summary(high_values)
        return {
            "trade_count": gross["trade_count"],
            "average_gross_r": gross["average_r"],
            "total_gross_r": gross["total_r"],
            "gross_profit_factor": gross["profit_factor_r"],
            "gross_positive_trade_rate": gross["positive_trade_rate"],
            "maximum_gross_drawdown_r": gross["maximum_drawdown_r"],
            "longest_gross_drawdown_duration_trades": gross[
                "longest_drawdown_duration_trades"
            ],
            "maximum_consecutive_losses": gross["maximum_consecutive_losses"],
            "average_high_cost_r": high["average_r"],
            "total_high_cost_r": high["total_r"],
            "high_cost_profit_factor": high["profit_factor_r"],
        }

    @staticmethod
    def _series_summary(values: Sequence[float]) -> dict[str, object]:
        if not values:
            return {
                "trade_count": 0, "average_r": None, "total_r": 0.0,
                "profit_factor_r": None, "positive_trade_rate": None,
                "maximum_drawdown_r": 0.0,
                "longest_drawdown_duration_trades": 0,
                "maximum_consecutive_losses": 0,
            }
        gains = sum(v for v in values if v > 0.0)
        losses = -sum(v for v in values if v < 0.0)
        equity = peak = maximum_drawdown = 0.0
        duration = longest_duration = streak = max_streak = 0
        for value in values:
            equity += value
            peak = max(peak, equity)
            drawdown = peak - equity
            maximum_drawdown = max(maximum_drawdown, drawdown)
            if drawdown > 1e-12:
                duration += 1
                longest_duration = max(longest_duration, duration)
            else:
                duration = 0
            if value < 0.0:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0
        return {
            "trade_count": len(values),
            "average_r": sum(values) / len(values),
            "total_r": sum(values),
            "profit_factor_r": gains / losses if losses else None,
            "positive_trade_rate": sum(v > 0.0 for v in values) / len(values),
            "maximum_drawdown_r": maximum_drawdown,
            "longest_drawdown_duration_trades": longest_duration,
            "maximum_consecutive_losses": max_streak,
        }

    def _deterioration_flags(
        self, summary: Mapping[str, object]
    ) -> list[str]:
        flags = []
        count = int(summary["trade_count"])
        average = summary["average_gross_r"]
        pf = summary["gross_profit_factor"]
        high_average = summary["average_high_cost_r"]
        drawdown = float(summary["maximum_gross_drawdown_r"])
        if count < self.ROLLING_WINDOW_TRADES:
            flags.append("INSUFFICIENT_WINDOW_TRADES")
        if average is not None and float(average) <= 0.0:
            flags.append("NON_POSITIVE_EXPECTANCY")
        if pf is not None and float(pf) < 1.0:
            flags.append("PROFIT_FACTOR_BELOW_ONE")
        if high_average is not None and float(high_average) <= 0.0:
            flags.append("NON_POSITIVE_HIGH_COST_EXPECTANCY")
        if drawdown > self.REFERENCE_MAXIMUM_DRAWDOWN_R:
            flags.append("DRAWDOWN_EXCEEDS_REFERENCE")
        if average is not None and float(average) < self.REFERENCE_AVERAGE_R * 0.5:
            flags.append("EXPECTANCY_BELOW_HALF_REFERENCE")
        return flags

    @staticmethod
    def _payload_row(row: Mapping[str, object]) -> dict[str, object]:
        return {str(k).lower().replace(" ", "_"): v for k, v in row.items()}
