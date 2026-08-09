"""Closed-candle multi-timeframe market-data synchronization."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from math import isfinite

import MetaTrader5 as mt5

from core.multi_timeframe.enums import Timeframe
from core.multi_timeframe.history_alignment import (
    bar_close_time,
    clip_history,
    completed_period_buckets,
    normalize_utc,
    required_bar_count,
    utc_week_start,
    visible_bars,
)
from core.regime_detector.models import MarketBar
from core.trading_pipeline.market_context import MarketContext

from .history_loader import HistoryLoader
from .models import BacktestReplayContext, BacktestReplayWindow


class MultiTimeframeLoader:
    """Load deterministic overlapping M5/M15/H1/H4 source histories."""

    _KEY_TIMEFRAMES: Mapping[str, Timeframe] = {
        "m5": Timeframe.M5,
        "m15": Timeframe.M15,
        "h1": Timeframe.H1,
        "h4": Timeframe.H4,
    }
    _MT5_TIMEFRAMES: Mapping[str, int] = {
        "m5": mt5.TIMEFRAME_M5,
        "m15": mt5.TIMEFRAME_M15,
        "h1": mt5.TIMEFRAME_H1,
        "h4": mt5.TIMEFRAME_H4,
    }

    def __init__(
        self,
        loader: HistoryLoader | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.loader = loader or HistoryLoader()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._validate_clock(self._clock())

    def load(
        self,
        symbol: str,
        bars: int,
        *,
        end_time: datetime | None = None,
        warmup_bars: int = 200,
        analysis_window_bars: int = 500,
    ) -> BacktestReplayContext:
        """Load one aligned replay where ``bars`` means eligible M5 bars."""

        symbol_value = self._validate_symbol(symbol)
        eligible_count = self._validate_bar_count(bars)
        warmup_count = self._validate_nonnegative_count(
            warmup_bars,
            "warmup_bars",
        )
        analysis_count = self._validate_analysis_window(analysis_window_bars)
        now = normalize_utc(self._clock(), "clock")
        boundary = (
            normalize_utc(end_time, "end_time")
            if end_time is not None
            else now
        )
        if boundary > now:
            raise ValueError("end_time cannot be in the future")

        required_m5 = eligible_count + warmup_count + analysis_count
        pilot_m5 = self._load_one(
            symbol=symbol_value,
            key="m5",
            bars=required_m5 + 2,
            end_time=boundary,
        )
        pilot_m5 = list(
            visible_bars(
                pilot_m5,
                timeframe=Timeframe.M5,
                boundary=boundary,
            )
        )
        if len(pilot_m5) < required_m5:
            raise RuntimeError(
                "Insufficient M5 history for the requested eligible bars, "
                "analytical window, and synchronized warm-up."
            )

        pilot_eligible = pilot_m5[-eligible_count:]
        first_eligible = pilot_eligible[0].timestamp.astimezone(UTC)
        first_eligible_boundary = bar_close_time(
            pilot_eligible[0],
            Timeframe.M5,
        )

        pilot_h4 = self._load_one(
            symbol=symbol_value,
            key="h4",
            bars=analysis_count + 2,
            end_time=first_eligible_boundary,
        )
        pilot_h4 = list(
            visible_bars(
                pilot_h4,
                timeframe=Timeframe.H4,
                boundary=first_eligible_boundary,
            )
        )
        if len(pilot_h4) < analysis_count:
            raise RuntimeError(
                "Insufficient H4 history at the first eligible M5 boundary."
            )

        earliest_required_m5 = pilot_m5[-required_m5].timestamp.astimezone(UTC)
        earliest_required_h4 = pilot_h4[-analysis_count].timestamp.astimezone(UTC)
        source_start = min(
            utc_week_start(earliest_required_m5) - timedelta(days=7),
            utc_week_start(earliest_required_h4) - timedelta(days=7),
        )

        requested_counts = {
            key: required_bar_count(
                start=source_start,
                end=boundary,
                timeframe=timeframe,
            )
            for key, timeframe in self._KEY_TIMEFRAMES.items()
        }
        histories = self._load_histories(
            symbol=symbol_value,
            counts=requested_counts,
            end_time=boundary,
        )
        normalized = self._validate_histories(histories)
        clipped = {
            key: list(
                clip_history(
                    series,
                    timeframe=self._KEY_TIMEFRAMES[key],
                    start=source_start,
                    end=boundary,
                )
            )
            for key, series in normalized.items()
        }
        for key, values in clipped.items():
            if not values:
                raise RuntimeError(
                    f"No completed {key.upper()} candles overlap the replay window."
                )

        final_eligible = clipped["m5"][-eligible_count:]
        if len(final_eligible) != eligible_count:
            raise RuntimeError(
                "Insufficient overlapping M5 history for the requested decisions."
            )
        if tuple(bar.timestamp for bar in final_eligible) != tuple(
            bar.timestamp for bar in pilot_eligible
        ):
            raise RuntimeError(
                "The selected M5 decision series changed during aligned loading."
            )

        if not self._snapshot_complete(
            histories=clipped,
            boundary=first_eligible_boundary,
            analysis_window_bars=analysis_count,
        ):
            raise RuntimeError(
                "Required M5/M15/H1/H4/D1/W1 history is incomplete at the "
                "first eligible M5 boundary."
            )

        available_warmup = sum(
            self._snapshot_complete(
                histories=clipped,
                boundary=bar_close_time(bar, Timeframe.M5),
                analysis_window_bars=analysis_count,
            )
            for bar in clipped["m5"]
            if bar.timestamp.astimezone(UTC) < first_eligible
        )
        if available_warmup < warmup_count:
            raise RuntimeError(
                "Insufficient complete synchronized M5 warm-up snapshots: "
                f"required={warmup_count} available={available_warmup}."
            )

        replay_window = BacktestReplayWindow(
            source_start=source_start,
            source_end=boundary,
            first_eligible_m5_timestamp=first_eligible,
            last_eligible_m5_timestamp=final_eligible[-1].timestamp.astimezone(UTC),
            requested_eligible_m5_bars=eligible_count,
            analysis_window_bars=analysis_count,
            required_warmup_snapshots=warmup_count,
            available_warmup_snapshots=available_warmup,
            requested_bar_counts=tuple(sorted(requested_counts.items())),
        )
        return BacktestReplayContext(
            current_bar=final_eligible[-1],
            m5_bars=clipped["m5"],
            m15_bars=clipped["m15"],
            h1_bars=clipped["h1"],
            h4_bars=clipped["h4"],
            replay_window=replay_window,
        )

    def synchronize_at(
        self,
        *,
        histories: Mapping[str, Sequence[MarketBar]],
        observation_timestamp: datetime,
    ) -> MarketContext:
        """Build a no-lookahead snapshot for one completed M5 observation."""

        normalized = self._validate_histories(histories)
        observation_open = normalize_utc(
            observation_timestamp,
            "observation_timestamp",
        )
        m5_bar = next(
            (
                bar
                for bar in normalized["m5"]
                if bar.timestamp.astimezone(UTC) == observation_open
            ),
            None,
        )
        if m5_bar is None:
            raise ValueError(
                "observation_timestamp must match an existing M5 candle open"
            )
        boundary = bar_close_time(m5_bar, Timeframe.M5)
        synchronized = {
            key: list(
                visible_bars(
                    series,
                    timeframe=self._KEY_TIMEFRAMES[key],
                    boundary=boundary,
                )
            )
            for key, series in normalized.items()
        }
        for key in self._KEY_TIMEFRAMES:
            if not synchronized[key]:
                raise RuntimeError(
                    f"No completed {key.upper()} candles are available at "
                    f"{observation_open.isoformat()}."
                )
        if synchronized["m5"][-1].timestamp.astimezone(UTC) != observation_open:
            raise RuntimeError(
                "M5 synchronization included a candle after the observation"
            )
        return MarketContext(
            current_bar=m5_bar,
            m5_bars=synchronized["m5"],
            m15_bars=synchronized["m15"],
            h1_bars=synchronized["h1"],
            h4_bars=synchronized["h4"],
        )

    def iter_synchronized(
        self,
        *,
        histories: Mapping[str, Sequence[MarketBar]],
        start_timestamp: datetime | None = None,
        end_timestamp: datetime | None = None,
    ) -> Iterator[MarketContext]:
        """Yield chronological no-lookahead snapshots for completed M5 bars."""

        normalized = self._validate_histories(histories)
        start = (
            normalize_utc(start_timestamp, "start_timestamp")
            if start_timestamp is not None
            else None
        )
        end = (
            normalize_utc(end_timestamp, "end_timestamp")
            if end_timestamp is not None
            else None
        )
        if start is not None and end is not None and start > end:
            raise ValueError("start_timestamp must not be after end_timestamp")

        for bar in normalized["m5"]:
            timestamp = bar.timestamp.astimezone(UTC)
            if start is not None and timestamp < start:
                continue
            if end is not None and timestamp > end:
                continue
            try:
                yield self.synchronize_at(
                    histories=normalized,
                    observation_timestamp=timestamp,
                )
            except RuntimeError:
                continue

    def _load_histories(
        self,
        *,
        symbol: str,
        counts: Mapping[str, int],
        end_time: datetime,
    ) -> dict[str, list[MarketBar]]:
        return {
            key: self._load_one(
                symbol=symbol,
                key=key,
                bars=counts[key],
                end_time=end_time,
            )
            for key in self._KEY_TIMEFRAMES
        }

    def _load_one(
        self,
        *,
        symbol: str,
        key: str,
        bars: int,
        end_time: datetime,
    ) -> list[MarketBar]:
        return self.loader.load_history(
            symbol=symbol,
            timeframe=self._MT5_TIMEFRAMES[key],
            bars=bars,
            end_time=end_time,
        )

    def _snapshot_complete(
        self,
        *,
        histories: Mapping[str, Sequence[MarketBar]],
        boundary: datetime,
        analysis_window_bars: int,
    ) -> bool:
        visible: dict[str, tuple[MarketBar, ...]] = {}
        for key, timeframe in self._KEY_TIMEFRAMES.items():
            values = visible_bars(
                histories[key],
                timeframe=timeframe,
                boundary=boundary,
                window_bars=analysis_window_bars,
            )
            if len(values) < analysis_window_bars:
                return False
            visible[key] = values

        h4 = visible["h4"]
        return bool(
            completed_period_buckets(
                h4,
                boundary=boundary,
                weekly=False,
            )
            and completed_period_buckets(
                h4,
                boundary=boundary,
                weekly=True,
            )
        )

    def _validate_histories(
        self,
        histories: Mapping[str, Sequence[MarketBar]],
    ) -> dict[str, tuple[MarketBar, ...]]:
        if not isinstance(histories, Mapping):
            raise TypeError("histories must be a mapping")

        expected = set(self._KEY_TIMEFRAMES)
        missing = expected.difference(histories)
        unexpected = set(histories).difference(expected)
        if missing:
            raise ValueError(
                "Missing timeframe histories: " + ", ".join(sorted(missing))
            )
        if unexpected:
            raise ValueError(
                "Unexpected timeframe histories: "
                + ", ".join(sorted(unexpected))
            )

        normalized: dict[str, tuple[MarketBar, ...]] = {}
        for key in self._KEY_TIMEFRAMES:
            series = histories[key]
            if isinstance(series, (str, bytes)) or not isinstance(series, Sequence):
                raise TypeError(f"{key} history must be a sequence of MarketBar")
            if not series:
                raise ValueError(f"{key} history cannot be empty")

            validated: list[MarketBar] = []
            previous: datetime | None = None
            for bar in series:
                self._validate_bar(bar, key)
                timestamp = normalize_utc(bar.timestamp, f"{key} timestamp")
                if previous is not None and timestamp <= previous:
                    raise ValueError(
                        f"{key} timestamps must be strictly increasing"
                    )
                previous = timestamp
                validated.append(bar)
            normalized[key] = tuple(validated)
        return normalized

    @staticmethod
    def _validate_symbol(symbol: str) -> str:
        if not isinstance(symbol, str):
            raise TypeError("symbol must be a string")
        normalized = symbol.strip()
        if not normalized:
            raise ValueError("symbol cannot be empty")
        return normalized

    @staticmethod
    def _validate_bar_count(bars: int) -> int:
        if isinstance(bars, bool) or not isinstance(bars, int):
            raise TypeError("bars must be an integer")
        if bars < 2:
            raise ValueError("bars must be at least 2")
        return bars

    @staticmethod
    def _validate_nonnegative_count(value: int, field_name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{field_name} must be an integer")
        if value < 0:
            raise ValueError(f"{field_name} cannot be negative")
        return value

    @staticmethod
    def _validate_analysis_window(value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("analysis_window_bars must be an integer")
        if value < 2:
            raise ValueError("analysis_window_bars must be at least 2")
        return value

    @staticmethod
    def _validate_clock(value: datetime) -> None:
        normalize_utc(value, "clock")

    @staticmethod
    def _validate_bar(bar: MarketBar, timeframe_name: str) -> None:
        if not isinstance(bar, MarketBar):
            raise TypeError(
                f"{timeframe_name} history values must be MarketBar instances"
            )
        normalize_utc(bar.timestamp, f"{timeframe_name} timestamp")
        for field_name in ("open", "high", "low", "close"):
            value = getattr(bar, field_name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(
                    f"{timeframe_name} {field_name} must be numeric"
                )
            if not isfinite(float(value)):
                raise ValueError(
                    f"{timeframe_name} {field_name} must be finite"
                )
        if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close):
            raise ValueError(f"{timeframe_name} candle geometry is invalid")
        if bar.low <= 0.0:
            raise ValueError(f"{timeframe_name} prices must be positive")
