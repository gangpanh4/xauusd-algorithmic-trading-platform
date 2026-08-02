"""Research-only execution diagnostics for frozen SMC Variant B."""

from __future__ import annotations

import csv
import json
from bisect import bisect_right
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path
from statistics import mean, median
from typing import Final

from core.strategies.methodology_models import MethodologyDirection

from .methodology_observer import MethodologyObservation


class MethodologyVariantBExecutionDiagnostics:
    """Measure execution-path behavior without authorizing trades."""

    VARIANT: Final[str] = (
        "VARIANT_B_BEARISH_EXCLUDE_COMPATIBLE_SWEEP"
    )
    HORIZON_BARS: Final[int] = 24
    STOP_DISTANCE: Final[float] = 2.5
    ENTRY_DELAYS: Final[tuple[int, ...]] = (0, 1, 2, 3)
    R_LEVELS: Final[tuple[float, ...]] = (0.5, 1.0, 1.5, 2.0)
    ATR_PERIOD: Final[int] = 14

    _CSV_COLUMNS: Final[tuple[str, ...]] = (
        "Variant",
        "Observation Timestamp",
        "Entry Delay Bars",
        "Entry Timestamp",
        "Entry Price",
        "Next Bar Range",
        "ATR 14",
        "Stop Distance ATR Multiple",
        "Maximum Favorable Excursion",
        "Maximum Adverse Excursion",
        "Terminal Directional Move",
        "Terminal Directional Return Percent",
        "First 0.5R Bar",
        "First 1.0R Bar",
        "First 1.5R Bar",
        "First 2.0R Bar",
        "0.5R Same Candle Dual Touch",
        "1.0R Same Candle Dual Touch",
        "1.5R Same Candle Dual Touch",
        "2.0R Same Candle Dual Touch",
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
        payload, rows = self.calculate(
            observations,
            m5_bars,
            window_metadata=window_metadata,
        )

        csv_path = (
            self.output_directory
            / "methodology_variant_b_execution_diagnostics.csv"
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
            / "methodology_variant_b_execution_diagnostics.json"
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
            if self._is_candidate(item)
        )
        bars = tuple(
            sorted(
                m5_bars,
                key=self._timestamp,
            )
        )
        timestamps = tuple(self._timestamp(bar) for bar in bars)
        self._validate_chronology(timestamps)

        rows: list[dict[str, object]] = []
        unavailable_by_delay = {
            delay: 0
            for delay in self.ENTRY_DELAYS
        }

        for candidate in candidates:
            base_index = bisect_right(
                timestamps,
                candidate.timestamp.astimezone(UTC),
            )
            for delay in self.ENTRY_DELAYS:
                entry_index = base_index + delay
                horizon_end = entry_index + self.HORIZON_BARS - 1
                if entry_index >= len(bars) or horizon_end >= len(bars):
                    unavailable_by_delay[delay] += 1
                    continue
                rows.append(
                    self._diagnose(
                        candidate=candidate,
                        bars=bars,
                        entry_index=entry_index,
                        delay=delay,
                    )
                )

        delay_summaries = [
            self._summarize_delay(delay, rows)
            for delay in self.ENTRY_DELAYS
        ]
        payload = {
            "variant": self.VARIANT,
            "candidate_count": len(candidates),
            "horizon_bars": self.HORIZON_BARS,
            "fixed_stop_distance_price_units": self.STOP_DISTANCE,
            "entry_delays_bars": list(self.ENTRY_DELAYS),
            "r_levels": list(self.R_LEVELS),
            "atr_period": self.ATR_PERIOD,
            "delay_summaries": delay_summaries,
            "unavailable_candidate_count_by_delay": {
                str(delay): unavailable_by_delay[delay]
                for delay in self.ENTRY_DELAYS
            },
            "same_candle_dual_touch_interpretation": (
                "OHLC cannot determine intrabar order; counts are diagnostic "
                "only and do not reclassify outcomes"
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

    def _diagnose(
        self,
        *,
        candidate: MethodologyObservation,
        bars: tuple[object, ...],
        entry_index: int,
        delay: int,
    ) -> dict[str, object]:
        entry_bar = bars[entry_index]
        entry_price = self._number(entry_bar, "open")
        horizon = bars[
            entry_index : entry_index + self.HORIZON_BARS
        ]
        atr = self._atr(bars, entry_index)

        lowest = min(self._number(bar, "low") for bar in horizon)
        highest = max(self._number(bar, "high") for bar in horizon)
        terminal_close = self._number(horizon[-1], "close")

        mfe = max(0.0, entry_price - lowest)
        mae = max(0.0, highest - entry_price)
        directional_move = entry_price - terminal_close
        directional_return = (
            directional_move / entry_price * 100.0
        )

        first_hits: dict[float, int | None] = {}
        dual_touches: dict[float, bool] = {}
        stop_level = entry_price + self.STOP_DISTANCE

        for level in self.R_LEVELS:
            target = entry_price - self.STOP_DISTANCE * level
            first_hit: int | None = None
            dual_touch = False
            for bar_number, bar in enumerate(horizon, start=1):
                high = self._number(bar, "high")
                low = self._number(bar, "low")
                stop_hit = high >= stop_level
                target_hit = low <= target
                if stop_hit and target_hit:
                    dual_touch = True
                if first_hit is None and target_hit:
                    first_hit = bar_number
            first_hits[level] = first_hit
            dual_touches[level] = dual_touch

        return {
            "Variant": self.VARIANT,
            "Observation Timestamp": (
                candidate.timestamp.astimezone(UTC).isoformat()
            ),
            "Entry Delay Bars": delay,
            "Entry Timestamp": self._timestamp(entry_bar).isoformat(),
            "Entry Price": entry_price,
            "Next Bar Range": (
                self._number(entry_bar, "high")
                - self._number(entry_bar, "low")
            ),
            "ATR 14": atr,
            "Stop Distance ATR Multiple": (
                self.STOP_DISTANCE / atr
                if atr is not None and atr > 0.0
                else None
            ),
            "Maximum Favorable Excursion": mfe,
            "Maximum Adverse Excursion": mae,
            "Terminal Directional Move": directional_move,
            "Terminal Directional Return Percent": directional_return,
            "First 0.5R Bar": first_hits[0.5],
            "First 1.0R Bar": first_hits[1.0],
            "First 1.5R Bar": first_hits[1.5],
            "First 2.0R Bar": first_hits[2.0],
            "0.5R Same Candle Dual Touch": dual_touches[0.5],
            "1.0R Same Candle Dual Touch": dual_touches[1.0],
            "1.5R Same Candle Dual Touch": dual_touches[1.5],
            "2.0R Same Candle Dual Touch": dual_touches[2.0],
            "Session": candidate.context.session_name,
            "Regime": candidate.context.regime_name,
        }

    def _summarize_delay(
        self,
        delay: int,
        rows: Sequence[Mapping[str, object]],
    ) -> dict[str, object]:
        selected = [
            row
            for row in rows
            if row["Entry Delay Bars"] == delay
        ]

        def values(name: str) -> list[float]:
            return [
                float(row[name])
                for row in selected
                if row[name] is not None
            ]

        level_summaries: dict[str, object] = {}
        for level in self.R_LEVELS:
            key = f"{level:.1f}R"
            first_key = f"First {level:.1f}R Bar"
            dual_key = f"{level:.1f}R Same Candle Dual Touch"
            hits = [
                int(row[first_key])
                for row in selected
                if row[first_key] is not None
            ]
            dual_count = sum(
                bool(row[dual_key])
                for row in selected
            )
            level_summaries[key] = {
                "reached_count": len(hits),
                "reached_rate": (
                    len(hits) / len(selected)
                    if selected
                    else None
                ),
                "median_first_reach_bar": (
                    median(hits)
                    if hits
                    else None
                ),
                "same_candle_dual_touch_count": dual_count,
                "same_candle_dual_touch_rate": (
                    dual_count / len(selected)
                    if selected
                    else None
                ),
            }

        mfe = values("Maximum Favorable Excursion")
        mae = values("Maximum Adverse Excursion")
        ranges = values("Next Bar Range")
        atrs = values("ATR 14")
        stop_atr = values("Stop Distance ATR Multiple")
        returns = values("Terminal Directional Return Percent")

        return {
            "entry_delay_bars": delay,
            "sample_count": len(selected),
            "average_next_bar_range": (
                mean(ranges) if ranges else None
            ),
            "median_next_bar_range": (
                median(ranges) if ranges else None
            ),
            "average_atr_14": mean(atrs) if atrs else None,
            "median_atr_14": median(atrs) if atrs else None,
            "average_stop_distance_atr_multiple": (
                mean(stop_atr) if stop_atr else None
            ),
            "median_stop_distance_atr_multiple": (
                median(stop_atr) if stop_atr else None
            ),
            "average_mfe": mean(mfe) if mfe else None,
            "median_mfe": median(mfe) if mfe else None,
            "average_mae": mean(mae) if mae else None,
            "median_mae": median(mae) if mae else None,
            "average_terminal_directional_return_percent": (
                mean(returns) if returns else None
            ),
            "median_terminal_directional_return_percent": (
                median(returns) if returns else None
            ),
            "r_level_diagnostics": level_summaries,
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
