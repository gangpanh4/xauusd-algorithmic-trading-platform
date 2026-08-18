"""Deterministic live freshness policy for read-only Aurum snapshots."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import pairwise
from typing import TYPE_CHECKING

from core.multi_timeframe.enums import Timeframe
from core.multi_timeframe.history_alignment import (
    TimestampedBar,
    completed_period_buckets,
    normalize_utc,
    timeframe_duration,
    utc_day_start,
)

from .enums import AurumDataMode
from .freshness import FreshnessAssessment, FreshnessContext

if TYPE_CHECKING:
    from .models import AurumReadModelV1

AURUM_LIVE_FRESHNESS_V1 = "AURUM_LIVE_FRESHNESS_V1"
MAX_QUOTE_AGE_SECONDS = 15.0
MAX_M5_DECISION_DELAY_SECONDS = 30.0

_REQUIRED_TIMEFRAMES = (
    Timeframe.M5,
    Timeframe.M15,
    Timeframe.H1,
    Timeframe.H4,
    Timeframe.DAILY,
    Timeframe.WEEKLY,
)
_INTRADAY_TARGETS = (
    Timeframe.M15,
    Timeframe.H1,
    Timeframe.H4,
)
_HTF_FAILURES = (
    (Timeframe.M15, "LIVE_M15_STALE"),
    (Timeframe.H1, "LIVE_H1_STALE"),
    (Timeframe.H4, "LIVE_H4_STALE"),
    (Timeframe.DAILY, "LIVE_D1_STALE"),
    (Timeframe.WEEKLY, "LIVE_W1_STALE"),
)


@dataclass(frozen=True, slots=True)
class _TimestampEvidence(TimestampedBar):
    """Timestamp-only structural evidence for repository period helpers."""

    timestamp: datetime


def _failure(reason_code: str, reason: str) -> FreshnessAssessment:
    return FreshnessAssessment(
        policy_id=AURUM_LIVE_FRESHNESS_V1,
        valid=False,
        critical_failure=True,
        reason_code=reason_code,
        reason=reason,
    )


def _invalid(reason: str) -> FreshnessAssessment:
    return _failure("LIVE_FRESHNESS_CONTEXT_INVALID", reason)


def _normalize_histories(
    values: Mapping[Timeframe, Sequence[datetime]],
) -> dict[Timeframe, tuple[datetime, ...]] | None:
    normalized: dict[Timeframe, tuple[datetime, ...]] = {}
    for timeframe in _REQUIRED_TIMEFRAMES:
        raw = values.get(timeframe)
        if (
            raw is None
            or not isinstance(raw, Sequence)
            or isinstance(raw, (str, bytes))
        ):
            return None
        timestamps = tuple(
            normalize_utc(
                value,
                f"bar_timestamps_by_timeframe[{timeframe.value}]",
            )
            for value in raw
        )
        if not timestamps:
            return None
        if any(
            current <= previous
            for previous, current in pairwise(timestamps)
        ):
            raise ValueError(
                f"{timeframe.value} freshness timestamps must increase strictly"
            )
        normalized[timeframe] = timestamps
    return normalized


def _containing_bucket_open(timestamp: datetime, timeframe: Timeframe) -> datetime:
    duration = timeframe_duration(timeframe)
    day_start = utc_day_start(timestamp)
    bucket_index = (timestamp - day_start) // duration
    return day_start + (bucket_index * duration)


def _expected_intraday_from_m5(
    m5_timestamps: Sequence[datetime],
    *,
    boundary: datetime,
    timeframe: Timeframe,
) -> datetime | None:
    duration = timeframe_duration(timeframe)
    expected: datetime | None = None
    for timestamp in m5_timestamps:
        bucket_open = _containing_bucket_open(timestamp, timeframe)
        if bucket_open + duration <= boundary:
            expected = bucket_open
    return expected


def _expected_derived_period_from_h4(
    h4_timestamps: Sequence[datetime],
    *,
    boundary: datetime,
    weekly: bool,
) -> datetime | None:
    evidence: tuple[TimestampedBar, ...] = tuple(
        _TimestampEvidence(timestamp=value) for value in h4_timestamps
    )
    completed = completed_period_buckets(
        evidence,
        boundary=boundary,
        weekly=weekly,
    )
    return completed[-1][0] if completed else None


def _derive_expected_htf_timestamps(
    histories: Mapping[Timeframe, Sequence[datetime]],
    *,
    boundary: datetime,
) -> dict[Timeframe, datetime] | None:
    expected: dict[Timeframe, datetime] = {}
    m5_timestamps = histories[Timeframe.M5]
    for timeframe in _INTRADAY_TARGETS:
        value = _expected_intraday_from_m5(
            m5_timestamps,
            boundary=boundary,
            timeframe=timeframe,
        )
        if value is None:
            return None
        expected[timeframe] = value

    h4_timestamps = histories[Timeframe.H4]
    daily = _expected_derived_period_from_h4(
        h4_timestamps,
        boundary=boundary,
        weekly=False,
    )
    weekly = _expected_derived_period_from_h4(
        h4_timestamps,
        boundary=boundary,
        weekly=True,
    )
    if daily is None or weekly is None:
        return None
    expected[Timeframe.DAILY] = daily
    expected[Timeframe.WEEKLY] = weekly
    return expected


class AurumLiveFreshnessPolicyV1:
    """Evaluate approved live temporal evidence without reading market data."""

    policy_id = AURUM_LIVE_FRESHNESS_V1

    def evaluate(self, context: FreshnessContext) -> FreshnessAssessment:
        """Return the first deterministic freshness failure, or a valid verdict."""

        if context.mode is not AurumDataMode.REAL_READ_ONLY:
            return _invalid(
                "AURUM_LIVE_FRESHNESS_V1 supports REAL_READ_ONLY mode only."
            )
        if not isinstance(context.symbol, str) or not context.symbol.strip():
            return _invalid("Live freshness requires a non-empty symbol.")
        if not isinstance(context.quote_available, bool):
            return _invalid("quote_available must be boolean.")
        if not isinstance(context.bar_timestamps_by_timeframe, Mapping):
            return _invalid("Timeframe timestamp evidence must be a mapping.")

        try:
            generated_at = normalize_utc(
                context.generated_at_utc,
                "generated_at_utc",
            )
            observation_time = normalize_utc(
                context.observation_time_utc,
                "observation_time_utc",
            )
            decision_available_at = normalize_utc(
                context.decision_available_at_utc,
                "decision_available_at_utc",
            )
            histories = _normalize_histories(context.bar_timestamps_by_timeframe)
        except (TypeError, ValueError):
            return _invalid(
                "Live freshness timestamps must be valid timezone-aware chronology."
            )

        if histories is None:
            return _invalid("Required live timeframe timestamp evidence is missing.")
        if decision_available_at != observation_time + timedelta(minutes=5):
            return _invalid(
                "M5 decision availability must equal observation time plus "
                "five minutes."
            )
        if generated_at < decision_available_at:
            return _invalid(
                "Snapshot generation cannot precede M5 decision availability."
            )
        if histories[Timeframe.M5][-1] != observation_time:
            return _invalid("Latest M5 timestamp must equal the observation timestamp.")

        try:
            expected_htf = _derive_expected_htf_timestamps(
                histories,
                boundary=decision_available_at,
            )
        except (TypeError, ValueError):
            return _invalid("Higher-timeframe evidence cannot be derived safely.")
        if expected_htf is None:
            return _invalid("Insufficient lower-timeframe evidence for freshness.")

        for timeframe, _ in _HTF_FAILURES:
            actual = histories[timeframe][-1]
            if actual > expected_htf[timeframe]:
                return _invalid(
                    f"Latest {timeframe.value} timestamp is newer than "
                    "lower-timeframe evidence permits."
                )

        quote_timestamp: datetime | None = None
        if context.quote_available:
            if context.quote_timestamp_utc is None:
                return _invalid("Available live quote requires a quote timestamp.")
            try:
                quote_timestamp = normalize_utc(
                    context.quote_timestamp_utc,
                    "quote_timestamp_utc",
                )
            except (TypeError, ValueError):
                return _invalid("Live quote timestamp must be timezone-aware.")

        if not context.quote_available:
            return _failure(
                "LIVE_QUOTE_UNAVAILABLE",
                "A current live quote is unavailable.",
            )

        if quote_timestamp is None:
            return _invalid("Available live quote requires a quote timestamp.")
        quote_age = (generated_at - quote_timestamp).total_seconds()
        if quote_age > MAX_QUOTE_AGE_SECONDS:
            return _failure(
                "LIVE_QUOTE_STALE",
                "Live quote age exceeds 15 seconds.",
            )

        m5_delay = (generated_at - decision_available_at).total_seconds()
        if m5_delay > MAX_M5_DECISION_DELAY_SECONDS:
            return _failure(
                "LIVE_M5_STALE",
                "M5 decision delay exceeds 30 seconds.",
            )

        for timeframe, reason_code in _HTF_FAILURES:
            actual = histories[timeframe][-1]
            if actual < expected_htf[timeframe]:
                return _failure(
                    reason_code,
                    f"Latest {timeframe.value} completed period is stale.",
                )

        return FreshnessAssessment(
            policy_id=AURUM_LIVE_FRESHNESS_V1,
            valid=True,
            critical_failure=False,
            reason_code=None,
            reason=None,
        )


@dataclass(frozen=True, slots=True)
class SnapshotCurrentness:
    """Read-time currentness verdict for one immutable live snapshot."""

    current: bool
    reason_code: str | None = None


def _not_current(reason_code: str) -> SnapshotCurrentness:
    return SnapshotCurrentness(current=False, reason_code=reason_code)


def evaluate_live_snapshot_currentness(
    snapshot: AurumReadModelV1,
    *,
    now_utc: datetime,
) -> SnapshotCurrentness:
    """Re-evaluate only quote and M5 time decay for a published snapshot."""

    try:
        now = normalize_utc(now_utc, "now_utc")
        quote = snapshot.quote
        meta = snapshot.meta
        quote_available = quote.available
        decision_available_at = normalize_utc(
            meta.decision_available_at_utc,
            "snapshot.meta.decision_available_at_utc",
        )
    except (AttributeError, TypeError, ValueError):
        return _not_current("LIVE_FRESHNESS_CONTEXT_INVALID")

    if not isinstance(quote_available, bool):
        return _not_current("LIVE_FRESHNESS_CONTEXT_INVALID")
    if decision_available_at > now:
        return _not_current("LIVE_FRESHNESS_CONTEXT_INVALID")

    if not quote_available:
        return _not_current("LIVE_QUOTE_UNAVAILABLE")

    quote_timestamp = quote.observed_at_utc
    if quote_timestamp is None:
        return _not_current("LIVE_FRESHNESS_CONTEXT_INVALID")
    try:
        quote_timestamp = normalize_utc(
            quote_timestamp,
            "snapshot.quote.observed_at_utc",
        )
    except (TypeError, ValueError):
        return _not_current("LIVE_FRESHNESS_CONTEXT_INVALID")
    if quote_timestamp > now:
        return _not_current("LIVE_FRESHNESS_CONTEXT_INVALID")

    current_quote_age = (now - quote_timestamp).total_seconds()
    if current_quote_age > MAX_QUOTE_AGE_SECONDS:
        return _not_current("LIVE_QUOTE_STALE")

    current_m5_delay = (now - decision_available_at).total_seconds()
    if current_m5_delay > MAX_M5_DECISION_DELAY_SECONDS:
        return _not_current("LIVE_M5_STALE")

    return SnapshotCurrentness(current=True)
