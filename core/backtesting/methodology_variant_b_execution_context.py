"""Execution-context diagnostics for frozen Variant B scenarios."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import mean
from typing import Final

from .methodology_observer import MethodologyObservation
from .methodology_variant_b_atr_shadow_matrix import (
    MethodologyVariantBATRShadowMatrix,
    VariantBATRShadowResult,
)


class MethodologyVariantBExecutionContext:
    """Describe session, regime, and candidate-overlap concentration."""

    VARIANT: Final[str] = (
        "VARIANT_B_BEARISH_EXCLUDE_COMPATIBLE_SWEEP"
    )
    FROZEN_SCENARIOS: Final[tuple[tuple[float, float], ...]] = (
        (1.0, 1.5),
        (1.0, 2.0),
    )

    _CSV_COLUMNS: Final[tuple[str, ...]] = (
        "Variant",
        "Stop ATR Multiple",
        "Target R",
        "Dimension",
        "Group",
        "Trade Count",
        "Trade Share",
        "Average R",
        "Total R",
        "Positive Trade Rate",
        "Profit Factor R",
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
            / "methodology_variant_b_execution_context.csv"
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
            / "methodology_variant_b_execution_context.json"
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
        matrix_payload, matrix_results = self.matrix.calculate(
            observations,
            m5_bars,
            window_metadata=window_metadata,
        )

        rows: list[dict[str, object]] = []
        scenario_summaries: list[dict[str, object]] = []

        for stop_multiple, target_r in self.FROZEN_SCENARIOS:
            results = [
                item
                for item in matrix_results
                if item.stop_atr_multiple == stop_multiple
                and item.target_r == target_r
            ]
            session_rows = self._group_rows(
                results,
                stop_multiple=stop_multiple,
                target_r=target_r,
                dimension="SESSION",
                key=lambda item: item.session or "UNKNOWN",
            )
            regime_rows = self._group_rows(
                results,
                stop_multiple=stop_multiple,
                target_r=target_r,
                dimension="REGIME",
                key=lambda item: item.regime or "UNKNOWN",
            )
            rows.extend(session_rows)
            rows.extend(regime_rows)

            scenario = next(
                (
                    item
                    for item in matrix_payload["scenarios"]
                    if item["stop_atr_multiple"] == stop_multiple
                    and item["target_r"] == target_r
                ),
                None,
            )
            if scenario is None:
                continue

            candidate_count = int(scenario["candidate_count"])
            executed = int(scenario["executed_shadow_trade_count"])
            skipped = int(
                scenario[
                    "candidates_skipped_while_shadow_position_open"
                ]
            )
            scenario_summaries.append(
                {
                    "stop_atr_multiple": stop_multiple,
                    "target_r": target_r,
                    "candidate_count": candidate_count,
                    "executed_shadow_trade_count": executed,
                    "overlapping_candidate_count": skipped,
                    "overlapping_candidate_rate": (
                        skipped / candidate_count
                        if candidate_count
                        else None
                    ),
                    "execution_coverage_rate": (
                        executed / candidate_count
                        if candidate_count
                        else None
                    ),
                    "average_holding_bars": scenario[
                        "average_holding_bars"
                    ],
                    "session_group_count": len(session_rows),
                    "regime_group_count": len(regime_rows),
                }
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
            "scenario_overlap_summaries": scenario_summaries,
            "group_results": rows,
            "capability_status": {
                "session_breakdown": "AVAILABLE",
                "regime_breakdown": "AVAILABLE",
                "overlapping_candidate_concentration": "AVAILABLE",
                "historical_entry_spread_series": "UNAVAILABLE",
                "historical_news_calendar": "UNAVAILABLE",
            },
            "unsupported_measurements": [
                {
                    "measurement": "ACTUAL_MT5_SPREAD_AT_ENTRY",
                    "reason": (
                        "The active historical research inputs do not expose "
                        "a persisted bid/ask or spread value for each entry."
                    ),
                },
                {
                    "measurement": "NEWS_PERIOD_SEPARATION",
                    "reason": (
                        "No connected historical economic-calendar dataset "
                        "is present in the active methodology research path."
                    ),
                },
            ],
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

    def _group_rows(
        self,
        results: Sequence[VariantBATRShadowResult],
        *,
        stop_multiple: float,
        target_r: float,
        dimension: str,
        key,
    ) -> list[dict[str, object]]:
        groups: dict[str, list[VariantBATRShadowResult]] = defaultdict(list)
        for result in results:
            groups[str(key(result))].append(result)

        total_count = len(results)
        rows: list[dict[str, object]] = []
        for name in sorted(groups):
            group = groups[name]
            values = [item.result_r for item in group]
            gains = sum(value for value in values if value > 0.0)
            losses = -sum(value for value in values if value < 0.0)
            rows.append(
                {
                    "Variant": self.VARIANT,
                    "Stop ATR Multiple": stop_multiple,
                    "Target R": target_r,
                    "Dimension": dimension,
                    "Group": name,
                    "Trade Count": len(group),
                    "Trade Share": (
                        len(group) / total_count
                        if total_count
                        else None
                    ),
                    "Average R": mean(values) if values else None,
                    "Total R": sum(values),
                    "Positive Trade Rate": (
                        sum(value > 0.0 for value in values)
                        / len(values)
                        if values
                        else None
                    ),
                    "Profit Factor R": (
                        gains / losses
                        if losses > 0.0
                        else None
                    ),
                }
            )
        return rows
