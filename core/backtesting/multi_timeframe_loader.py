"""Closed-candle multi-timeframe market-data synchronization."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from math import isfinite

import MetaTrader5 as mt5

from core.regime_detector.models import MarketBar
from core.trading_pipeline.market_context import MarketContext

from .history_loader import HistoryLoader


class MultiTimeframeLoader:
    """Load and synchronize completed M5, M15, H1, and H4 candles.

    ``MarketBar.timestamp`` is treated as the candle *open* timestamp. A bar is
    visible to a historical observation only after ``timestamp + duration``.
    This prevents an M15 observation from seeing an H1/H4 candle that has
    opened but has not yet closed.
    """

    _DURATIONS: Mapping[str, timedelta] = {
        "m5": timedelta(minutes=5),
        "m15": timedelta(minutes=15),
        "h1": timedelta(hours=1),
        "h4": timedelta(hours=4),
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

    def load(self, symbol: str, bars: int) -> MarketContext:
        """Load histories and return the latest fully synchronized snapshot.

        The current still-forming broker candle is excluded using the injected
        UTC clock. The latest completed M15 candle defines the observation.
        """

        symbol_value = self._validate_symbol(symbol)
        bar_count = self._validate_bar_count(bars)
        histories = self._load_histories(symbol_value, bar_count)
        now = self._normalize_utc(self._clock(), "clock")

        completed = {
            name: self._completed_by(name, series, now)
            for name, series in histories.items()
        }
        if not completed["m15"]:
            raise RuntimeError("No completed M15 candles are available.")

        observation_bar = completed["m15"][-1]
        return self.synchronize_at(
            histories=completed,
            observation_timestamp=observation_bar.timestamp,
        )

    def synchronize_at(
        self,
        *,
        histories: Mapping[str, Sequence[MarketBar]],
        observation_timestamp: datetime,
    ) -> MarketContext:
        """Build a no-lookahead snapshot for one completed M15 observation.

        ``observation_timestamp`` must identify an existing M15 candle open.
        The visibility boundary is that candle's close time. Every included bar
        must have closed on or before that boundary.
        """

        normalized = self._validate_histories(histories)
        observation_open = self._normalize_utc(
            observation_timestamp,
            "observation_timestamp",
        )
        observation_close = observation_open + self._DURATIONS["m15"]

        m15_bar = next(
            (bar for bar in normalized["m15"] if bar.timestamp == observation_open),
            None,
        )
        if m15_bar is None:
            raise ValueError(
                "observation_timestamp must match an existing M15 candle open"
            )

        synchronized = {
            name: self._completed_by(name, series, observation_close)
            for name, series in normalized.items()
        }

        for name in self._DURATIONS:
            if not synchronized[name]:
                raise RuntimeError(
                    f"No completed {name.upper()} candles are available at "
                    f"{observation_open.isoformat()}."
                )

        if synchronized["m15"][-1].timestamp != observation_open:
            raise RuntimeError(
                "M15 synchronization included a candle after the observation"
            )

        return MarketContext(
            current_bar=m15_bar,
            m5_bars=list(synchronized["m5"]),
            m15_bars=list(synchronized["m15"]),
            h1_bars=list(synchronized["h1"]),
            h4_bars=list(synchronized["h4"]),
        )

    def iter_synchronized(
        self,
        *,
        histories: Mapping[str, Sequence[MarketBar]],
        start_timestamp: datetime | None = None,
        end_timestamp: datetime | None = None,
    ) -> Iterator[MarketContext]:
        """Yield chronological no-lookahead snapshots for completed M15 bars."""

        normalized = self._validate_histories(histories)
        start = (
            self._normalize_utc(start_timestamp, "start_timestamp")
            if start_timestamp is not None
            else None
        )
        end = (
            self._normalize_utc(end_timestamp, "end_timestamp")
            if end_timestamp is not None
            else None
        )
        if start is not None and end is not None and start > end:
            raise ValueError("start_timestamp must not be after end_timestamp")

        for bar in normalized["m15"]:
            if start is not None and bar.timestamp < start:
                continue
            if end is not None and bar.timestamp > end:
                continue
            try:
                yield self.synchronize_at(
                    histories=normalized,
                    observation_timestamp=bar.timestamp,
                )
            except RuntimeError:
                # Early M15 observations may predate the first completed H1/H4
                # candle. They are warm-up-incomplete, not valid snapshots.
                continue

    def _load_histories(
        self,
        symbol: str,
        bars: int,
    ) -> dict[str, list[MarketBar]]:
        mapping = {
            "m5": mt5.TIMEFRAME_M5,
            "m15": mt5.TIMEFRAME_M15,
            "h1": mt5.TIMEFRAME_H1,
            "h4": mt5.TIMEFRAME_H4,
        }
        return {
            name: self.loader.load_history(
                symbol=symbol,
                timeframe=timeframe,
                bars=bars,
            )
            for name, timeframe in mapping.items()
        }

    def _validate_histories(
        self,
        histories: Mapping[str, Sequence[MarketBar]],
    ) -> dict[str, tuple[MarketBar, ...]]:
        if not isinstance(histories, Mapping):
            raise TypeError("histories must be a mapping")

        expected = set(self._DURATIONS)
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
        for name in self._DURATIONS:
            series = histories[name]
            if isinstance(series, (str, bytes)) or not isinstance(series, Sequence):
                raise TypeError(f"{name} history must be a sequence of MarketBar")
            if not series:
                raise ValueError(f"{name} history cannot be empty")

            validated: list[MarketBar] = []
            previous: datetime | None = None
            for bar in series:
                self._validate_bar(bar, name)
                timestamp = self._normalize_utc(bar.timestamp, f"{name} timestamp")
                if previous is not None and timestamp <= previous:
                    raise ValueError(
                        f"{name} timestamps must be strictly increasing"
                    )
                previous = timestamp
                validated.append(bar)
            normalized[name] = tuple(validated)

        return normalized

    def _completed_by(
        self,
        timeframe_name: str,
        bars: Sequence[MarketBar],
        visibility_boundary: datetime,
    ) -> tuple[MarketBar, ...]:
        duration = self._DURATIONS[timeframe_name]
        boundary = self._normalize_utc(
            visibility_boundary,
            "visibility_boundary",
        )
        return tuple(
            bar
            for bar in bars
            if self._normalize_utc(bar.timestamp, "bar timestamp") + duration
            <= boundary
        )

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
    def _validate_clock(value: datetime) -> None:
        MultiTimeframeLoader._normalize_utc(value, "clock")

    @staticmethod
    def _normalize_utc(value: datetime, field_name: str) -> datetime:
        if not isinstance(value, datetime):
            raise TypeError(f"{field_name} must be a datetime")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field_name} must be timezone-aware")
        return value.astimezone(UTC)

    @staticmethod
    def _validate_bar(bar: MarketBar, timeframe_name: str) -> None:
        if not isinstance(bar, MarketBar):
            raise TypeError(
                f"{timeframe_name} history values must be MarketBar instances"
            )
        MultiTimeframeLoader._normalize_utc(
            bar.timestamp,
            f"{timeframe_name} timestamp",
        )
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
