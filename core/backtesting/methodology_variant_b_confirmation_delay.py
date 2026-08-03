"""Causal confirmation-delay research for frozen Variant B."""
from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from statistics import mean
from typing import Final

from .methodology_observer import MethodologyObservation
from .methodology_variant_b_atr_shadow_matrix import (
    MethodologyVariantBATRShadowMatrix,
    VariantBATRShadowResult,
)


class MethodologyVariantBConfirmationDelay:
    """Approximate late-cluster timing using causal confirmation rules."""

    VARIANT: Final[str] = (
        "VARIANT_B_BEARISH_EXCLUDE_COMPATIBLE_SWEEP"
    )
    STOP_ATR_MULTIPLE: Final[float] = 1.0
    TARGET_R: Final[float] = 2.0

    _CSV_COLUMNS: Final[tuple[str, ...]] = (
        "Variant",
        "Rule",
        "Causal",
        "Original Candidate Count",
        "Confirmed Candidate Count",
        "Executed Shadow Trade Count",
        "Candidate Retention Rate",
        "Execution Coverage Rate",
        "Average Confirmation Delay Minutes",
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
            / "methodology_variant_b_confirmation_delay.csv"
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
            / "methodology_variant_b_confirmation_delay.json"
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

        rules = (
            (
                "BASELINE_FIRST_AVAILABLE_WHILE_FLAT",
                tuple((item, 0.0) for item in candidates),
            ),
            (
                "QUIET_CONFIRMATION_5_MINUTES",
                self._quiet_confirmation(candidates, 5),
            ),
            (
                "QUIET_CONFIRMATION_10_MINUTES",
                self._quiet_confirmation(candidates, 10),
            ),
            (
                "FIRST_AFTER_15_MINUTE_QUIET_PERIOD",
                self._first_after_quiet_period(candidates, 15),
            ),
            (
                "PERSISTENCE_2_CONSECUTIVE",
                self._persistence(candidates, 2),
            ),
            (
                "PERSISTENCE_3_CONSECUTIVE",
                self._persistence(candidates, 3),
            ),
        )

        rows: list[dict[str, object]] = []
        for rule_name, confirmed in rules:
            shifted = tuple(item for item, _ in confirmed)
            delays = tuple(delay for _, delay in confirmed)

            _, matrix_results = self.matrix.calculate(
                shifted,
                m5_bars,
                window_metadata=window_metadata,
            )
            scenario_results = [
                result
                for result in matrix_results
                if result.stop_atr_multiple == self.STOP_ATR_MULTIPLE
                and result.target_r == self.TARGET_R
            ]
            rows.append(
                self._summarize(
                    rule_name=rule_name,
                    original_candidate_count=len(candidates),
                    confirmed_candidate_count=len(shifted),
                    delays=delays,
                    results=scenario_results,
                )
            )

        payload = {
            "variant": self.VARIANT,
            "frozen_scenario": {
                "stop_atr_multiple": self.STOP_ATR_MULTIPLE,
                "target_r": self.TARGET_R,
            },
            "rules": rows,
            "rule_definitions": [
                {
                    "rule": "QUIET_CONFIRMATION_5_MINUTES",
                    "definition": (
                        "Wait 5 minutes after a candidate and confirm "
                        "only if no newer candidate arrives during the wait."
                    ),
                },
                {
                    "rule": "QUIET_CONFIRMATION_10_MINUTES",
                    "definition": (
                        "Wait 10 minutes after a candidate and confirm "
                        "only if no newer candidate arrives during the wait."
                    ),
                },
                {
                    "rule": "FIRST_AFTER_15_MINUTE_QUIET_PERIOD",
                    "definition": (
                        "Select the first candidate after at least "
                        "15 minutes without a candidate."
                    ),
                },
                {
                    "rule": "PERSISTENCE_2_CONSECUTIVE",
                    "definition": (
                        "Confirm once when two candidates occur at "
                        "consecutive 5-minute observations."
                    ),
                },
                {
                    "rule": "PERSISTENCE_3_CONSECUTIVE",
                    "definition": (
                        "Confirm once when three candidates occur at "
                        "consecutive 5-minute observations."
                    ),
                },
            ],
            "causality_note": (
                "All tested rules use only timestamps known at or before "
                "the confirmation timestamp."
            ),
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

    def _quiet_confirmation(
        self,
        candidates: tuple[MethodologyObservation, ...],
        wait_minutes: int,
    ) -> tuple[tuple[MethodologyObservation, float], ...]:
        wait = timedelta(minutes=wait_minutes)
        confirmed: list[tuple[MethodologyObservation, float]] = []

        for index, candidate in enumerate(candidates):
            confirmation_time = candidate.timestamp + wait
            next_timestamp = (
                candidates[index + 1].timestamp
                if index + 1 < len(candidates)
                else None
            )
            if (
                next_timestamp is not None
                and next_timestamp <= confirmation_time
            ):
                continue

            confirmed.append(
                (
                    self._shift_observation(
                        candidate,
                        confirmation_time,
                    ),
                    float(wait_minutes),
                )
            )

        return tuple(confirmed)

    @staticmethod
    def _first_after_quiet_period(
        candidates: tuple[MethodologyObservation, ...],
        quiet_minutes: int,
    ) -> tuple[tuple[MethodologyObservation, float], ...]:
        if not candidates:
            return ()

        quiet = timedelta(minutes=quiet_minutes)
        selected: list[tuple[MethodologyObservation, float]] = [
            (candidates[0], 0.0)
        ]
        for previous, candidate in zip(
            candidates,
            candidates[1:],
        ):
            if candidate.timestamp - previous.timestamp >= quiet:
                selected.append((candidate, 0.0))

        return tuple(selected)

    @staticmethod
    def _persistence(
        candidates: tuple[MethodologyObservation, ...],
        required_count: int,
    ) -> tuple[tuple[MethodologyObservation, float], ...]:
        if not candidates:
            return ()

        exact_gap = timedelta(minutes=5)
        selected: list[tuple[MethodologyObservation, float]] = []
        streak = 1
        confirmed_in_streak = False

        for previous, candidate in zip(
            candidates,
            candidates[1:],
        ):
            if candidate.timestamp - previous.timestamp == exact_gap:
                streak += 1
            else:
                streak = 1
                confirmed_in_streak = False

            if streak >= required_count and not confirmed_in_streak:
                selected.append(
                    (
                        candidate,
                        float((required_count - 1) * 5),
                    )
                )
                confirmed_in_streak = True

        return tuple(selected)

    @staticmethod
    def _shift_observation(
        observation: MethodologyObservation,
        timestamp,
    ) -> MethodologyObservation:
        return replace(
            observation,
            timestamp=timestamp,
            context=replace(
                observation.context,
                timestamp=timestamp,
            ),
            smc=replace(
                observation.smc,
                timestamp=timestamp,
            ),
            ict=replace(
                observation.ict,
                timestamp=timestamp,
            ),
        )

    def _summarize(
        self,
        *,
        rule_name: str,
        original_candidate_count: int,
        confirmed_candidate_count: int,
        delays: Sequence[float],
        results: Sequence[VariantBATRShadowResult],
    ) -> dict[str, object]:
        values = [result.result_r for result in results]
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
            "Causal": True,
            "Original Candidate Count": original_candidate_count,
            "Confirmed Candidate Count": confirmed_candidate_count,
            "Executed Shadow Trade Count": len(results),
            "Candidate Retention Rate": (
                confirmed_candidate_count / original_candidate_count
                if original_candidate_count
                else None
            ),
            "Execution Coverage Rate": (
                len(results) / confirmed_candidate_count
                if confirmed_candidate_count
                else None
            ),
            "Average Confirmation Delay Minutes": (
                mean(delays) if delays else None
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
                mean(result.holding_bars for result in results)
                if results
                else None
            ),
        }
