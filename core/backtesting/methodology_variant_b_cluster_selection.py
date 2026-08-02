"""Cluster-selection research for frozen Variant B."""

from __future__ import annotations

import csv
import json
from collections.abc import Callable, Mapping, Sequence
from datetime import timedelta
from pathlib import Path
from statistics import mean
from typing import Final

from .methodology_observer import MethodologyObservation
from .methodology_variant_b_atr_shadow_matrix import (
    MethodologyVariantBATRShadowMatrix,
    VariantBATRShadowResult,
)


class MethodologyVariantBClusterSelection:
    """Compare predeclared candidate de-duplication rules."""

    VARIANT: Final[str] = (
        "VARIANT_B_BEARISH_EXCLUDE_COMPATIBLE_SWEEP"
    )
    STOP_ATR_MULTIPLE: Final[float] = 1.0
    TARGET_R: Final[float] = 2.0
    CLUSTER_GAP_MINUTES: Final[int] = 15

    _CSV_COLUMNS: Final[tuple[str, ...]] = (
        "Variant",
        "Rule",
        "Causal",
        "Selected Candidate Count",
        "Executed Shadow Trade Count",
        "Candidate Retention Rate",
        "Execution Coverage Rate",
        "Average R",
        "Total R",
        "Profit Factor R",
        "Maximum Drawdown R",
        "Positive Trade Rate",
        "Average Holding Bars",
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
            / "methodology_variant_b_cluster_selection.csv"
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
            / "methodology_variant_b_cluster_selection.json"
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
        candidates = tuple(
            item
            for item in sorted(
                observations,
                key=lambda value: value.timestamp,
            )
            if self.matrix._is_candidate(item)
        )

        rules: tuple[
            tuple[
                str,
                bool,
                Callable[
                    [tuple[MethodologyObservation, ...]],
                    tuple[MethodologyObservation, ...],
                ],
            ],
            ...,
        ] = (
            ("BASELINE_FIRST_AVAILABLE_WHILE_FLAT", True, lambda values: values),
            (
                "FIRST_IN_15_MINUTE_CLUSTER",
                True,
                self._first_in_cluster,
            ),
            (
                "LAST_IN_15_MINUTE_CLUSTER",
                False,
                self._last_in_cluster,
            ),
            (
                "COOLDOWN_15_MINUTES",
                True,
                lambda values: self._cooldown(values, 15),
            ),
            (
                "COOLDOWN_30_MINUTES",
                True,
                lambda values: self._cooldown(values, 30),
            ),
        )

        rows: list[dict[str, object]] = []
        for rule_name, causal, selector in rules:
            selected = selector(candidates)
            _, results = self.matrix.calculate(
                selected,
                m5_bars,
                window_metadata=window_metadata,
            )
            scenario_results = [
                item
                for item in results
                if item.stop_atr_multiple == self.STOP_ATR_MULTIPLE
                and item.target_r == self.TARGET_R
            ]
            rows.append(
                self._summarize(
                    rule_name=rule_name,
                    causal=causal,
                    total_candidates=len(candidates),
                    selected_candidates=len(selected),
                    results=scenario_results,
                )
            )

        payload = {
            "variant": self.VARIANT,
            "frozen_scenario": {
                "stop_atr_multiple": self.STOP_ATR_MULTIPLE,
                "target_r": self.TARGET_R,
            },
            "cluster_definition": (
                "Consecutive Variant B candidates belong to one cluster "
                "when the gap from the previous candidate is 15 minutes "
                "or less."
            ),
            "rules": rows,
            "unsupported_rules": [
                {
                    "rule": "BEST_SCORE_IN_CLUSTER",
                    "status": "UNAVAILABLE",
                    "reason": (
                        "The frozen Variant B methodology observation does "
                        "not expose a validated scalar ranking score."
                    ),
                }
            ],
            "retrospective_rules": [
                {
                    "rule": "LAST_IN_15_MINUTE_CLUSTER",
                    "deployable": False,
                    "reason": (
                        "Selecting the last candidate requires knowing that "
                        "no further candidate will arrive inside the cluster "
                        "gap, so it is non-causal."
                    ),
                }
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

    def _first_in_cluster(
        self,
        candidates: tuple[MethodologyObservation, ...],
    ) -> tuple[MethodologyObservation, ...]:
        clusters = self._clusters(candidates)
        return tuple(cluster[0] for cluster in clusters)

    def _last_in_cluster(
        self,
        candidates: tuple[MethodologyObservation, ...],
    ) -> tuple[MethodologyObservation, ...]:
        clusters = self._clusters(candidates)
        return tuple(cluster[-1] for cluster in clusters)

    def _clusters(
        self,
        candidates: tuple[MethodologyObservation, ...],
    ) -> tuple[tuple[MethodologyObservation, ...], ...]:
        if not candidates:
            return ()

        gap = timedelta(minutes=self.CLUSTER_GAP_MINUTES)
        clusters: list[list[MethodologyObservation]] = [[candidates[0]]]
        for candidate in candidates[1:]:
            if candidate.timestamp - clusters[-1][-1].timestamp <= gap:
                clusters[-1].append(candidate)
            else:
                clusters.append([candidate])
        return tuple(tuple(cluster) for cluster in clusters)

    @staticmethod
    def _cooldown(
        candidates: tuple[MethodologyObservation, ...],
        minutes: int,
    ) -> tuple[MethodologyObservation, ...]:
        selected: list[MethodologyObservation] = []
        cooldown = timedelta(minutes=minutes)
        for candidate in candidates:
            if (
                not selected
                or candidate.timestamp - selected[-1].timestamp >= cooldown
            ):
                selected.append(candidate)
        return tuple(selected)

    def _summarize(
        self,
        *,
        rule_name: str,
        causal: bool,
        total_candidates: int,
        selected_candidates: int,
        results: Sequence[VariantBATRShadowResult],
    ) -> dict[str, object]:
        values = [item.result_r for item in results]
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
            "Variant": self.VARIANT,
            "Rule": rule_name,
            "Causal": causal,
            "Selected Candidate Count": selected_candidates,
            "Executed Shadow Trade Count": len(results),
            "Candidate Retention Rate": (
                selected_candidates / total_candidates
                if total_candidates
                else None
            ),
            "Execution Coverage Rate": (
                len(results) / selected_candidates
                if selected_candidates
                else None
            ),
            "Average R": mean(values) if values else None,
            "Total R": sum(values),
            "Profit Factor R": (
                gains / losses
                if losses > 0.0
                else None
            ),
            "Maximum Drawdown R": maximum_drawdown,
            "Positive Trade Rate": (
                sum(value > 0.0 for value in values) / len(values)
                if values
                else None
            ),
            "Average Holding Bars": (
                mean(item.holding_bars for item in results)
                if results
                else None
            ),
        }
