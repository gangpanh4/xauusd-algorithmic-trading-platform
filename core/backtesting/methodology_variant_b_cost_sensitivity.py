"""Cost sensitivity for frozen Variant B ATR shadow scenarios."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import mean, median
from typing import Final

from .methodology_observer import MethodologyObservation
from .methodology_variant_b_atr_shadow_matrix import (
    MethodologyVariantBATRShadowMatrix,
    VariantBATRShadowResult,
)


class MethodologyVariantBCostSensitivity:
    """Apply transparent round-trip cost stresses to frozen scenarios."""

    VARIANT: Final[str] = (
        "VARIANT_B_BEARISH_EXCLUDE_COMPATIBLE_SWEEP"
    )
    FROZEN_SCENARIOS: Final[tuple[tuple[float, float], ...]] = (
        (1.0, 1.5),
        (1.0, 2.0),
    )
    ROUND_TRIP_COST_PRICE_UNITS: Final[
        tuple[tuple[str, float], ...]
    ] = (
        ("ZERO_COST", 0.00),
        ("LOW_COST", 0.10),
        ("MEDIUM_COST", 0.25),
        ("HIGH_COST", 0.50),
        ("STRESS_COST", 1.00),
    )

    _CSV_COLUMNS: Final[tuple[str, ...]] = (
        "Variant",
        "Stop ATR Multiple",
        "Target R",
        "Cost Scenario",
        "Round Trip Cost Price Units",
        "Trade Count",
        "Average Net R",
        "Median Net R",
        "Total Net R",
        "Profit Factor Net R",
        "Maximum Drawdown Net R",
        "Positive Trade Rate",
        "Average Cost R",
        "Maximum Cost R",
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
            / "methodology_variant_b_cost_sensitivity.csv"
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
            / "methodology_variant_b_cost_sensitivity.json"
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

        frozen = [
            result
            for result in matrix_results
            if (
                result.stop_atr_multiple,
                result.target_r,
            ) in self.FROZEN_SCENARIOS
        ]

        rows: list[dict[str, object]] = []
        for stop_multiple, target_r in self.FROZEN_SCENARIOS:
            scenario_results = [
                result
                for result in frozen
                if result.stop_atr_multiple == stop_multiple
                and result.target_r == target_r
            ]
            for cost_name, cost_price_units in (
                self.ROUND_TRIP_COST_PRICE_UNITS
            ):
                rows.append(
                    self._summarize(
                        stop_multiple=stop_multiple,
                        target_r=target_r,
                        cost_name=cost_name,
                        cost_price_units=cost_price_units,
                        results=scenario_results,
                    )
                )

        payload = {
            "variant": self.VARIANT,
            "frozen_scenarios": [
                {
                    "stop_atr_multiple": stop,
                    "target_r": target,
                }
                for stop, target in self.FROZEN_SCENARIOS
            ],
            "cost_scenarios": [
                {
                    "name": name,
                    "round_trip_cost_price_units": value,
                }
                for name, value in self.ROUND_TRIP_COST_PRICE_UNITS
            ],
            "cost_definition": (
                "Total adverse round-trip price cost applied once per "
                "completed shadow trade. This is a sensitivity grid, not a "
                "claim about any broker's actual spread, slippage, or fees."
            ),
            "results": rows,
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

    def _summarize(
        self,
        *,
        stop_multiple: float,
        target_r: float,
        cost_name: str,
        cost_price_units: float,
        results: Sequence[VariantBATRShadowResult],
    ) -> dict[str, object]:
        net_values: list[float] = []
        cost_values: list[float] = []

        for result in results:
            stop_distance = result.atr_14 * stop_multiple
            cost_r = (
                cost_price_units / stop_distance
                if stop_distance > 0.0
                else 0.0
            )
            cost_values.append(cost_r)
            net_values.append(result.result_r - cost_r)

        positive = sum(value for value in net_values if value > 0.0)
        negative = -sum(value for value in net_values if value < 0.0)

        equity = 0.0
        peak = 0.0
        maximum_drawdown = 0.0
        for value in net_values:
            equity += value
            peak = max(peak, equity)
            maximum_drawdown = max(
                maximum_drawdown,
                peak - equity,
            )

        return {
            "Variant": self.VARIANT,
            "Stop ATR Multiple": stop_multiple,
            "Target R": target_r,
            "Cost Scenario": cost_name,
            "Round Trip Cost Price Units": cost_price_units,
            "Trade Count": len(net_values),
            "Average Net R": (
                mean(net_values) if net_values else None
            ),
            "Median Net R": (
                median(net_values) if net_values else None
            ),
            "Total Net R": sum(net_values),
            "Profit Factor Net R": (
                positive / negative
                if negative > 0.0
                else None
            ),
            "Maximum Drawdown Net R": maximum_drawdown,
            "Positive Trade Rate": (
                sum(value > 0.0 for value in net_values)
                / len(net_values)
                if net_values
                else None
            ),
            "Average Cost R": (
                mean(cost_values) if cost_values else None
            ),
            "Maximum Cost R": (
                max(cost_values) if cost_values else None
            ),
        }
