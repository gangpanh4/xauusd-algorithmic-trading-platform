"""ATR-normalized research matrix for frozen SMC Variant B."""

from __future__ import annotations

import csv
import json
from bisect import bisect_right
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path
from statistics import mean, median
from typing import Final

from core.strategies.methodology_models import MethodologyDirection

from .methodology_observer import MethodologyObservation


@dataclass(frozen=True, slots=True)
class VariantBATRShadowResult:
    observation_timestamp: datetime
    entry_timestamp: datetime
    exit_timestamp: datetime
    stop_atr_multiple: float
    target_r: float
    atr_14: float
    entry_price: float
    stop_price: float
    target_price: float
    exit_price: float
    exit_reason: str
    holding_bars: int
    result_r: float
    same_candle_dual_touch: bool
    maximum_favorable_excursion_r: float
    maximum_adverse_excursion_r: float
    session: str
    regime: str


class MethodologyVariantBATRShadowMatrix:
    """Evaluate a fixed ATR stop/target matrix without trade authority."""

    VARIANT: Final[str] = (
        "VARIANT_B_BEARISH_EXCLUDE_COMPATIBLE_SWEEP"
    )
    ATR_PERIOD: Final[int] = 14
    STOP_ATR_MULTIPLES: Final[tuple[float, ...]] = (
        0.50,
        0.75,
        1.00,
        1.50,
    )
    TARGET_R_MULTIPLES: Final[tuple[float, ...]] = (
        1.0,
        1.5,
        2.0,
    )
    HORIZON_BARS: Final[int] = 24

    _CSV_COLUMNS: Final[tuple[str, ...]] = (
        "Variant",
        "Observation Timestamp",
        "Entry Timestamp",
        "Exit Timestamp",
        "Stop ATR Multiple",
        "Target R",
        "ATR 14",
        "Entry Price",
        "Stop Price",
        "Target Price",
        "Exit Price",
        "Exit Reason",
        "Holding Bars",
        "Result R",
        "Same Candle Dual Touch",
        "Maximum Favorable Excursion R",
        "Maximum Adverse Excursion R",
        "Session",
        "Regime",
    )

    def __init__(
        self,
        output_directory: str | Path = "output/backtests",
    ) -> None:
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)

    def export(
        self,
        observations: Sequence[MethodologyObservation],
        m5_bars: Sequence[object],
        *,
        window_metadata: Mapping[str, object] | None = None,
    ) -> tuple[Path, Path]:
        payload, results = self.calculate(
            observations,
            m5_bars,
            window_metadata=window_metadata,
        )

        csv_path = (
            self.output_directory
            / "methodology_variant_b_atr_shadow_matrix.csv"
        )
        with csv_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=list(self._CSV_COLUMNS),
                extrasaction="raise",
            )
            writer.writeheader()
            writer.writerows(self._row(result) for result in results)

        json_path = (
            self.output_directory
            / "methodology_variant_b_atr_shadow_matrix.json"
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
    ) -> tuple[dict[str, object], tuple[VariantBATRShadowResult, ...]]:
        candidates = tuple(
            item
            for item in sorted(
                observations,
                key=lambda value: value.timestamp,
            )
            if self._is_candidate(item)
        )
        bars = tuple(sorted(m5_bars, key=self._timestamp))
        timestamps = tuple(self._timestamp(bar) for bar in bars)
        self._validate_chronology(timestamps)

        all_results: list[VariantBATRShadowResult] = []
        scenarios: list[dict[str, object]] = []

        for stop_multiple in self.STOP_ATR_MULTIPLES:
            for target_r in self.TARGET_R_MULTIPLES:
                scenario_results: list[VariantBATRShadowResult] = []
                skipped_while_open = 0
                unavailable_atr_or_horizon = 0
                active_until: datetime | None = None

                for candidate in candidates:
                    if (
                        active_until is not None
                        and candidate.timestamp <= active_until
                    ):
                        skipped_while_open += 1
                        continue

                    entry_index = bisect_right(
                        timestamps,
                        candidate.timestamp.astimezone(UTC),
                    )
                    if entry_index >= len(bars):
                        unavailable_atr_or_horizon += 1
                        continue

                    atr = self._atr(bars, entry_index)
                    horizon_end = entry_index + self.HORIZON_BARS - 1
                    if atr is None or horizon_end >= len(bars):
                        unavailable_atr_or_horizon += 1
                        continue

                    result = self._simulate(
                        candidate=candidate,
                        bars=bars,
                        entry_index=entry_index,
                        atr=atr,
                        stop_multiple=stop_multiple,
                        target_r=target_r,
                    )
                    scenario_results.append(result)
                    all_results.append(result)
                    active_until = result.exit_timestamp

                scenarios.append(
                    self._summarize(
                        stop_multiple=stop_multiple,
                        target_r=target_r,
                        candidate_count=len(candidates),
                        results=scenario_results,
                        skipped_while_open=skipped_while_open,
                        unavailable=unavailable_atr_or_horizon,
                    )
                )

        payload = {
            "variant": self.VARIANT,
            "direction": MethodologyDirection.BEARISH.value,
            "entry_policy": "NEXT_COMPLETED_M5_BAR_OPEN",
            "atr_period": self.ATR_PERIOD,
            "stop_atr_multiples": list(self.STOP_ATR_MULTIPLES),
            "target_r_multiples": list(self.TARGET_R_MULTIPLES),
            "horizon_bars": self.HORIZON_BARS,
            "candidate_count": len(candidates),
            "position_policy": (
                "ONE_SHADOW_POSITION_PER_STOP_TARGET_SCENARIO"
            ),
            "same_candle_policy": (
                "AMBIGUOUS_AND_CONSERVATIVE_STOP_FIRST"
            ),
            "scenarios": scenarios,
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
        return payload, tuple(all_results)

    def _simulate(
        self,
        *,
        candidate: MethodologyObservation,
        bars: tuple[object, ...],
        entry_index: int,
        atr: float,
        stop_multiple: float,
        target_r: float,
    ) -> VariantBATRShadowResult:
        entry_bar = bars[entry_index]
        entry_price = self._number(entry_bar, "open")
        stop_distance = atr * stop_multiple
        stop_price = entry_price + stop_distance
        target_price = entry_price - stop_distance * target_r

        final_index = entry_index + self.HORIZON_BARS - 1
        exit_index = final_index
        exit_price = self._number(bars[final_index], "close")
        exit_reason = "TIME_EXIT"
        same_candle_dual_touch = False
        lowest = entry_price
        highest = entry_price

        for index in range(entry_index, final_index + 1):
            bar = bars[index]
            high = self._number(bar, "high")
            low = self._number(bar, "low")
            highest = max(highest, high)
            lowest = min(lowest, low)

            stop_hit = high >= stop_price
            target_hit = low <= target_price
            if stop_hit and target_hit:
                same_candle_dual_touch = True
                exit_index = index
                exit_price = stop_price
                exit_reason = "AMBIGUOUS_STOP_FIRST"
                break
            if stop_hit:
                exit_index = index
                exit_price = stop_price
                exit_reason = "STOP_LOSS"
                break
            if target_hit:
                exit_index = index
                exit_price = target_price
                exit_reason = "TAKE_PROFIT"
                break

        result_r = (entry_price - exit_price) / stop_distance
        return VariantBATRShadowResult(
            observation_timestamp=candidate.timestamp.astimezone(UTC),
            entry_timestamp=self._timestamp(entry_bar),
            exit_timestamp=self._timestamp(bars[exit_index]),
            stop_atr_multiple=stop_multiple,
            target_r=target_r,
            atr_14=atr,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            exit_price=exit_price,
            exit_reason=exit_reason,
            holding_bars=exit_index - entry_index + 1,
            result_r=result_r,
            same_candle_dual_touch=same_candle_dual_touch,
            maximum_favorable_excursion_r=(
                max(0.0, entry_price - lowest) / stop_distance
            ),
            maximum_adverse_excursion_r=(
                max(0.0, highest - entry_price) / stop_distance
            ),
            session=candidate.context.session_name,
            regime=candidate.context.regime_name,
        )

    def _summarize(
        self,
        *,
        stop_multiple: float,
        target_r: float,
        candidate_count: int,
        results: Sequence[VariantBATRShadowResult],
        skipped_while_open: int,
        unavailable: int,
    ) -> dict[str, object]:
        stop_first = sum(
            result.exit_reason in {
                "STOP_LOSS",
                "AMBIGUOUS_STOP_FIRST",
            }
            for result in results
        )
        target_first = sum(
            result.exit_reason == "TAKE_PROFIT"
            for result in results
        )
        time_exits = sum(
            result.exit_reason == "TIME_EXIT"
            for result in results
        )
        ambiguous = sum(
            result.same_candle_dual_touch
            for result in results
        )
        positive_r = sum(
            result.result_r
            for result in results
            if result.result_r > 0.0
        )
        negative_r = -sum(
            result.result_r
            for result in results
            if result.result_r < 0.0
        )

        equity = 0.0
        peak = 0.0
        maximum_drawdown = 0.0
        for result in results:
            equity += result.result_r
            peak = max(peak, equity)
            maximum_drawdown = max(
                maximum_drawdown,
                peak - equity,
            )

        result_values = [result.result_r for result in results]
        return {
            "stop_atr_multiple": stop_multiple,
            "target_r": target_r,
            "candidate_count": candidate_count,
            "executed_shadow_trade_count": len(results),
            "sample_coverage_rate": (
                len(results) / candidate_count
                if candidate_count
                else None
            ),
            "candidates_skipped_while_shadow_position_open": (
                skipped_while_open
            ),
            "candidates_without_atr_or_complete_horizon": unavailable,
            "stop_first_count": stop_first,
            "stop_first_rate": (
                stop_first / len(results)
                if results
                else None
            ),
            "target_first_count": target_first,
            "target_first_rate": (
                target_first / len(results)
                if results
                else None
            ),
            "time_exit_count": time_exits,
            "time_exit_rate": (
                time_exits / len(results)
                if results
                else None
            ),
            "same_candle_ambiguity_count": ambiguous,
            "same_candle_ambiguity_rate": (
                ambiguous / len(results)
                if results
                else None
            ),
            "average_r": (
                mean(result_values)
                if result_values
                else None
            ),
            "median_r": (
                median(result_values)
                if result_values
                else None
            ),
            "total_r": sum(result_values),
            "profit_factor_r": (
                positive_r / negative_r
                if negative_r > 0.0
                else None
            ),
            "maximum_drawdown_r": maximum_drawdown,
            "average_holding_bars": (
                mean(result.holding_bars for result in results)
                if results
                else None
            ),
            "average_mfe_r": (
                mean(
                    result.maximum_favorable_excursion_r
                    for result in results
                )
                if results
                else None
            ),
            "average_mae_r": (
                mean(
                    result.maximum_adverse_excursion_r
                    for result in results
                )
                if results
                else None
            ),
            "exit_reason_counts": dict(
                sorted(
                    Counter(
                        result.exit_reason
                        for result in results
                    ).items()
                )
            ),
        }

    def _atr(
        self,
        bars: tuple[object, ...],
        entry_index: int,
    ) -> float | None:
        start = entry_index - self.ATR_PERIOD
        if start < 1:
            return None

        true_ranges: list[float] = []
        for index in range(start, entry_index):
            bar = bars[index]
            previous = bars[index - 1]
            high = self._number(bar, "high")
            low = self._number(bar, "low")
            previous_close = self._number(previous, "close")
            true_ranges.append(
                max(
                    high - low,
                    abs(high - previous_close),
                    abs(low - previous_close),
                )
            )
        return mean(true_ranges)

    @staticmethod
    def _is_candidate(item: MethodologyObservation) -> bool:
        return (
            item.smc.direction is MethodologyDirection.BEARISH
            and any(
                condition.code == "LIQUIDITY_SWEEP_COMPATIBLE"
                for condition in item.smc.failed_conditions
            )
        )

    def _row(
        self,
        result: VariantBATRShadowResult,
    ) -> dict[str, object]:
        return {
            "Variant": self.VARIANT,
            "Observation Timestamp": (
                result.observation_timestamp.isoformat()
            ),
            "Entry Timestamp": result.entry_timestamp.isoformat(),
            "Exit Timestamp": result.exit_timestamp.isoformat(),
            "Stop ATR Multiple": result.stop_atr_multiple,
            "Target R": result.target_r,
            "ATR 14": result.atr_14,
            "Entry Price": result.entry_price,
            "Stop Price": result.stop_price,
            "Target Price": result.target_price,
            "Exit Price": result.exit_price,
            "Exit Reason": result.exit_reason,
            "Holding Bars": result.holding_bars,
            "Result R": result.result_r,
            "Same Candle Dual Touch": (
                result.same_candle_dual_touch
            ),
            "Maximum Favorable Excursion R": (
                result.maximum_favorable_excursion_r
            ),
            "Maximum Adverse Excursion R": (
                result.maximum_adverse_excursion_r
            ),
            "Session": result.session,
            "Regime": result.regime,
        }

    @staticmethod
    def _timestamp(bar: object) -> datetime:
        value = getattr(bar, "timestamp", None)
        if not isinstance(value, datetime):
            raise TypeError("every M5 bar must expose a datetime timestamp")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("M5 bar timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @staticmethod
    def _number(bar: object, name: str) -> float:
        value = getattr(bar, name, None)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"every M5 bar must expose numeric {name}")
        result = float(value)
        if not isfinite(result) or result <= 0.0:
            raise ValueError(f"M5 bar {name} must be positive and finite")
        return result

    @staticmethod
    def _validate_chronology(
        timestamps: tuple[datetime, ...],
    ) -> None:
        if any(
            current <= previous
            for previous, current in zip(timestamps, timestamps[1:])
        ):
            raise ValueError(
                "M5 bar timestamps must be strictly increasing"
            )
