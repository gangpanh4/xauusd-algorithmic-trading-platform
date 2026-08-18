from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from core.aurum_presentation import live_freshness
from core.aurum_presentation.enums import AurumDataMode
from core.aurum_presentation.freshness import FreshnessAssessment, FreshnessContext
from core.aurum_presentation.live_freshness import (
    AURUM_LIVE_FRESHNESS_V1,
    MAX_M5_DECISION_DELAY_SECONDS,
    MAX_QUOTE_AGE_SECONDS,
    AurumLiveFreshnessPolicyV1,
    evaluate_live_snapshot_currentness,
)
from core.multi_timeframe.enums import Timeframe

_OBSERVATION = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)
_DECISION_AVAILABLE = _OBSERVATION + timedelta(minutes=5)
_GENERATED = _DECISION_AVAILABLE + timedelta(seconds=10)
_VALID_HISTORY = {
    Timeframe.M5: (
        datetime(2026, 8, 18, 4, 0, tzinfo=UTC),
        datetime(2026, 8, 18, 9, 0, tzinfo=UTC),
        datetime(2026, 8, 18, 9, 45, tzinfo=UTC),
        _OBSERVATION,
    ),
    Timeframe.M15: (datetime(2026, 8, 18, 9, 45, tzinfo=UTC),),
    Timeframe.H1: (datetime(2026, 8, 18, 9, 0, tzinfo=UTC),),
    Timeframe.H4: (
        datetime(2026, 8, 10, 0, 0, tzinfo=UTC),
        datetime(2026, 8, 17, 0, 0, tzinfo=UTC),
        datetime(2026, 8, 18, 4, 0, tzinfo=UTC),
    ),
    Timeframe.DAILY: (datetime(2026, 8, 17, 0, 0, tzinfo=UTC),),
    Timeframe.WEEKLY: (datetime(2026, 8, 10, 0, 0, tzinfo=UTC),),
}


def _copy_history(
    history: dict[Timeframe, tuple[datetime, ...]] | None = None,
) -> dict[Timeframe, tuple[datetime, ...]]:
    source = _VALID_HISTORY if history is None else history
    return {timeframe: tuple(values) for timeframe, values in source.items()}


def _replace_latest(
    history: dict[Timeframe, tuple[datetime, ...]],
    timeframe: Timeframe,
    value: datetime,
) -> dict[Timeframe, tuple[datetime, ...]]:
    result = _copy_history(history)
    result[timeframe] = (*result[timeframe][:-1], value)
    return result


def _context(
    *,
    mode: AurumDataMode = AurumDataMode.REAL_READ_ONLY,
    generated_at: datetime = _GENERATED,
    observation_time: datetime = _OBSERVATION,
    decision_available_at: datetime = _DECISION_AVAILABLE,
    quote_available: bool = True,
    quote_timestamp: datetime | None = None,
    history: dict[Timeframe, tuple[datetime, ...]] | None = None,
) -> FreshnessContext:
    if quote_timestamp is None and quote_available:
        quote_timestamp = generated_at - timedelta(seconds=1)
    return FreshnessContext(
        mode=mode,
        symbol="XAUUSD",
        generated_at_utc=generated_at,
        observation_time_utc=observation_time,
        decision_available_at_utc=decision_available_at,
        quote_available=quote_available,
        quote_timestamp_utc=quote_timestamp,
        bar_timestamps_by_timeframe=_copy_history(history),
    )


def _evaluate(context: FreshnessContext) -> FreshnessAssessment:
    return AurumLiveFreshnessPolicyV1().evaluate(context)


def test_valid_live_context_is_fresh() -> None:
    assessment = _evaluate(_context())

    assert assessment.policy_id == AURUM_LIVE_FRESHNESS_V1
    assert assessment.valid is True
    assert assessment.critical_failure is False
    assert assessment.reason_code is None
    assert assessment.reason is None


def test_exact_quote_age_threshold_passes() -> None:
    assessment = _evaluate(
        _context(
            quote_timestamp=_GENERATED
            - timedelta(seconds=MAX_QUOTE_AGE_SECONDS)
        )
    )

    assert assessment.valid is True


def test_quote_age_just_above_threshold_fails() -> None:
    assessment = _evaluate(
        _context(
            quote_timestamp=_GENERATED
            - timedelta(seconds=MAX_QUOTE_AGE_SECONDS, microseconds=1)
        )
    )

    assert assessment.reason_code == "LIVE_QUOTE_STALE"
    assert assessment.valid is False
    assert assessment.critical_failure is True


def test_exact_m5_decision_delay_threshold_passes() -> None:
    generated_at = _DECISION_AVAILABLE + timedelta(
        seconds=MAX_M5_DECISION_DELAY_SECONDS
    )
    assessment = _evaluate(
        _context(
            generated_at=generated_at,
            quote_timestamp=generated_at - timedelta(seconds=1),
        )
    )

    assert assessment.valid is True


def test_m5_decision_delay_just_above_threshold_fails() -> None:
    generated_at = _DECISION_AVAILABLE + timedelta(
        seconds=MAX_M5_DECISION_DELAY_SECONDS,
        microseconds=1,
    )
    assessment = _evaluate(
        _context(
            generated_at=generated_at,
            quote_timestamp=generated_at - timedelta(seconds=1),
        )
    )

    assert assessment.reason_code == "LIVE_M5_STALE"


def test_missing_quote_in_real_mode_is_unavailable() -> None:
    assessment = _evaluate(
        _context(quote_available=False, quote_timestamp=None)
    )

    assert assessment.reason_code == "LIVE_QUOTE_UNAVAILABLE"
    assert assessment.critical_failure is True


def test_stale_quote_is_critical() -> None:
    assessment = _evaluate(
        _context(quote_timestamp=_GENERATED - timedelta(seconds=16))
    )

    assert assessment.reason_code == "LIVE_QUOTE_STALE"
    assert assessment.critical_failure is True


def test_policy_does_not_reread_quote() -> None:
    source = inspect.getsource(live_freshness)

    assert "QuoteReader" not in source
    assert ".read(" not in source


def test_policy_has_no_mt5_dependency() -> None:
    source = inspect.getsource(live_freshness)

    assert "MetaTrader5" not in source
    assert "mt5." not in source


def test_valid_decision_availability_chronology_passes() -> None:
    assessment = _evaluate(_context())

    assert assessment.valid is True


def test_stale_m5_returns_live_m5_stale() -> None:
    generated_at = _DECISION_AVAILABLE + timedelta(seconds=31)
    assessment = _evaluate(
        _context(
            generated_at=generated_at,
            quote_timestamp=generated_at,
        )
    )

    assert assessment.reason_code == "LIVE_M5_STALE"


def test_normal_five_minute_candle_duration_is_not_m5_stale_age() -> None:
    generated_at = _OBSERVATION + timedelta(minutes=5, seconds=1)
    assessment = _evaluate(
        _context(
            generated_at=generated_at,
            quote_timestamp=generated_at,
        )
    )

    assert assessment.valid is True


@pytest.mark.parametrize(
    "timeframe",
    [
        Timeframe.M15,
        Timeframe.H1,
        Timeframe.H4,
        Timeframe.DAILY,
        Timeframe.WEEKLY,
    ],
)
def test_each_required_higher_timeframe_accepts_expected_completed_period(
    timeframe: Timeframe,
) -> None:
    assert _VALID_HISTORY[timeframe]
    assert _evaluate(_context()).valid is True


@pytest.mark.parametrize(
    ("timeframe", "reason_code", "older_by"),
    [
        (Timeframe.M15, "LIVE_M15_STALE", timedelta(minutes=15)),
        (Timeframe.H1, "LIVE_H1_STALE", timedelta(hours=1)),
        (Timeframe.H4, "LIVE_H4_STALE", timedelta(hours=4)),
        (Timeframe.DAILY, "LIVE_D1_STALE", timedelta(days=1)),
        (Timeframe.WEEKLY, "LIVE_W1_STALE", timedelta(days=7)),
    ],
)
def test_each_required_higher_timeframe_stale_code_is_exact(
    timeframe: Timeframe,
    reason_code: str,
    older_by: timedelta,
) -> None:
    history = _copy_history()
    stale = history[timeframe][-1] - older_by
    history = _replace_latest(history, timeframe, stale)

    assessment = _evaluate(_context(history=history))

    assert assessment.reason_code == reason_code
    assert assessment.valid is False
    assert assessment.critical_failure is True


def test_m15_exact_completion_boundary_uses_just_completed_evidence_bucket() -> None:
    observation = datetime(2026, 8, 18, 10, 10, tzinfo=UTC)
    boundary = datetime(2026, 8, 18, 10, 15, tzinfo=UTC)
    history = _copy_history()
    history[Timeframe.M5] = (*history[Timeframe.M5], observation)
    history = _replace_latest(
        history,
        Timeframe.M15,
        datetime(2026, 8, 18, 10, 0, tzinfo=UTC),
    )

    assessment = _evaluate(
        _context(
            observation_time=observation,
            decision_available_at=boundary,
            generated_at=boundary + timedelta(seconds=1),
            quote_timestamp=boundary,
            history=history,
        )
    )

    assert assessment.valid is True


def test_h1_exact_completion_boundary_uses_just_completed_evidence_bucket() -> None:
    observation = datetime(2026, 8, 18, 10, 55, tzinfo=UTC)
    boundary = datetime(2026, 8, 18, 11, 0, tzinfo=UTC)
    history = _copy_history()
    history[Timeframe.M5] = (*history[Timeframe.M5], observation)
    history = _replace_latest(
        history,
        Timeframe.M15,
        datetime(2026, 8, 18, 10, 45, tzinfo=UTC),
    )
    history = _replace_latest(
        history,
        Timeframe.H1,
        datetime(2026, 8, 18, 10, 0, tzinfo=UTC),
    )

    assessment = _evaluate(
        _context(
            observation_time=observation,
            decision_available_at=boundary,
            generated_at=boundary + timedelta(seconds=1),
            quote_timestamp=boundary,
            history=history,
        )
    )

    assert assessment.valid is True


def test_h4_exact_completion_boundary_uses_just_completed_evidence_bucket() -> None:
    observation = datetime(2026, 8, 18, 11, 55, tzinfo=UTC)
    boundary = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
    history = _copy_history()
    history[Timeframe.M5] = (*history[Timeframe.M5], observation)
    history = _replace_latest(
        history,
        Timeframe.M15,
        datetime(2026, 8, 18, 11, 45, tzinfo=UTC),
    )
    history = _replace_latest(
        history,
        Timeframe.H1,
        datetime(2026, 8, 18, 11, 0, tzinfo=UTC),
    )
    history = _replace_latest(
        history,
        Timeframe.H4,
        datetime(2026, 8, 18, 8, 0, tzinfo=UTC),
    )

    assessment = _evaluate(
        _context(
            observation_time=observation,
            decision_available_at=boundary,
            generated_at=boundary + timedelta(seconds=1),
            quote_timestamp=boundary,
            history=history,
        )
    )

    assert assessment.valid is True


def test_d1_exact_completion_boundary_uses_completed_h4_bucket() -> None:
    observation = datetime(2026, 8, 18, 23, 55, tzinfo=UTC)
    boundary = datetime(2026, 8, 19, 0, 0, tzinfo=UTC)
    history = _copy_history()
    history[Timeframe.M5] = (*history[Timeframe.M5], observation)
    history = _replace_latest(
        history,
        Timeframe.M15,
        datetime(2026, 8, 18, 23, 45, tzinfo=UTC),
    )
    history = _replace_latest(
        history,
        Timeframe.H1,
        datetime(2026, 8, 18, 23, 0, tzinfo=UTC),
    )
    history = _replace_latest(
        history,
        Timeframe.H4,
        datetime(2026, 8, 18, 20, 0, tzinfo=UTC),
    )
    history = _replace_latest(
        history,
        Timeframe.DAILY,
        datetime(2026, 8, 18, 0, 0, tzinfo=UTC),
    )

    assessment = _evaluate(
        _context(
            observation_time=observation,
            decision_available_at=boundary,
            generated_at=boundary + timedelta(seconds=1),
            quote_timestamp=boundary,
            history=history,
        )
    )

    assert assessment.valid is True


def test_w1_exact_completion_boundary_uses_completed_h4_bucket() -> None:
    observation = datetime(2026, 8, 23, 23, 55, tzinfo=UTC)
    boundary = datetime(2026, 8, 24, 0, 0, tzinfo=UTC)
    history = _copy_history()
    history[Timeframe.M5] = (
        datetime(2026, 8, 23, 20, 0, tzinfo=UTC),
        datetime(2026, 8, 23, 23, 0, tzinfo=UTC),
        datetime(2026, 8, 23, 23, 45, tzinfo=UTC),
        observation,
    )
    history[Timeframe.M15] = (datetime(2026, 8, 23, 23, 45, tzinfo=UTC),)
    history[Timeframe.H1] = (datetime(2026, 8, 23, 23, 0, tzinfo=UTC),)
    history[Timeframe.H4] = (
        datetime(2026, 8, 10, 0, 0, tzinfo=UTC),
        datetime(2026, 8, 17, 0, 0, tzinfo=UTC),
        datetime(2026, 8, 23, 20, 0, tzinfo=UTC),
    )
    history[Timeframe.DAILY] = (datetime(2026, 8, 23, 0, 0, tzinfo=UTC),)
    history[Timeframe.WEEKLY] = (datetime(2026, 8, 17, 0, 0, tzinfo=UTC),)

    assessment = _evaluate(
        _context(
            observation_time=observation,
            decision_available_at=boundary,
            generated_at=boundary + timedelta(seconds=1),
            quote_timestamp=boundary,
            history=history,
        )
    )

    assert assessment.valid is True


def test_missing_available_quote_timestamp_is_invalid_context() -> None:
    context = FreshnessContext(
        mode=AurumDataMode.REAL_READ_ONLY,
        symbol="XAUUSD",
        generated_at_utc=_GENERATED,
        observation_time_utc=_OBSERVATION,
        decision_available_at_utc=_DECISION_AVAILABLE,
        quote_available=True,
        quote_timestamp_utc=None,
        bar_timestamps_by_timeframe=_copy_history(),
    )

    assert _evaluate(context).reason_code == "LIVE_FRESHNESS_CONTEXT_INVALID"


def test_naive_timestamp_is_invalid_context() -> None:
    context = _context(
        generated_at=datetime(2026, 8, 18, 10, 5, 10),  # noqa: DTZ001
        quote_timestamp=datetime(2026, 8, 18, 10, 5, 9, tzinfo=UTC),
    )

    assert _evaluate(context).reason_code == "LIVE_FRESHNESS_CONTEXT_INVALID"


def test_missing_required_timeframe_is_invalid_context() -> None:
    history = _copy_history()
    del history[Timeframe.H4]

    assert (
        _evaluate(_context(history=history)).reason_code
        == "LIVE_FRESHNESS_CONTEXT_INVALID"
    )


def test_malformed_decision_availability_is_invalid_context() -> None:
    assessment = _evaluate(
        _context(
            decision_available_at=_OBSERVATION + timedelta(minutes=4, seconds=59)
        )
    )

    assert assessment.reason_code == "LIVE_FRESHNESS_CONTEXT_INVALID"


def test_generation_before_decision_availability_is_invalid_context() -> None:
    generated_at = _DECISION_AVAILABLE - timedelta(microseconds=1)
    assessment = _evaluate(
        _context(
            generated_at=generated_at,
            quote_timestamp=generated_at,
        )
    )

    assert assessment.reason_code == "LIVE_FRESHNESS_CONTEXT_INVALID"


def test_latest_m5_must_match_observation_or_context_is_invalid() -> None:
    history = _copy_history()
    history[Timeframe.M5] = history[Timeframe.M5][:-1]

    assert (
        _evaluate(_context(history=history)).reason_code
        == "LIVE_FRESHNESS_CONTEXT_INVALID"
    )


def test_duplicate_or_reversed_chronology_is_invalid_context() -> None:
    history = _copy_history()
    history[Timeframe.M5] = (*history[Timeframe.M5], history[Timeframe.M5][-1])

    assert (
        _evaluate(_context(history=history)).reason_code
        == "LIVE_FRESHNESS_CONTEXT_INVALID"
    )


def test_invalid_context_precedes_all_other_failures() -> None:
    assessment = _evaluate(
        _context(
            generated_at=datetime(2026, 8, 18, 10, 5, 31),  # noqa: DTZ001
            quote_available=False,
        )
    )

    assert assessment.reason_code == "LIVE_FRESHNESS_CONTEXT_INVALID"


def test_unavailable_quote_precedes_stale_m5() -> None:
    generated_at = _DECISION_AVAILABLE + timedelta(seconds=31)
    assessment = _evaluate(
        _context(
            generated_at=generated_at,
            quote_available=False,
            quote_timestamp=None,
        )
    )

    assert assessment.reason_code == "LIVE_QUOTE_UNAVAILABLE"


def test_stale_quote_precedes_stale_m5() -> None:
    generated_at = _DECISION_AVAILABLE + timedelta(seconds=31)
    assessment = _evaluate(
        _context(
            generated_at=generated_at,
            quote_timestamp=generated_at - timedelta(seconds=16),
        )
    )

    assert assessment.reason_code == "LIVE_QUOTE_STALE"


def test_stale_m5_precedes_higher_timeframe_failure() -> None:
    generated_at = _DECISION_AVAILABLE + timedelta(seconds=31)
    history = _replace_latest(
        _copy_history(),
        Timeframe.M15,
        datetime(2026, 8, 18, 9, 30, tzinfo=UTC),
    )
    assessment = _evaluate(
        _context(
            generated_at=generated_at,
            quote_timestamp=generated_at,
            history=history,
        )
    )

    assert assessment.reason_code == "LIVE_M5_STALE"


@pytest.mark.parametrize(
    ("stale_timeframes", "expected_code"),
    [
        (
            (
                Timeframe.M15,
                Timeframe.H1,
                Timeframe.H4,
                Timeframe.DAILY,
                Timeframe.WEEKLY,
            ),
            "LIVE_M15_STALE",
        ),
        (
            (Timeframe.H1, Timeframe.H4, Timeframe.DAILY, Timeframe.WEEKLY),
            "LIVE_H1_STALE",
        ),
        (
            (Timeframe.H4, Timeframe.DAILY, Timeframe.WEEKLY),
            "LIVE_H4_STALE",
        ),
        ((Timeframe.DAILY, Timeframe.WEEKLY), "LIVE_D1_STALE"),
        ((Timeframe.WEEKLY,), "LIVE_W1_STALE"),
    ],
)
def test_higher_timeframe_precedence_is_frozen(
    stale_timeframes: tuple[Timeframe, ...],
    expected_code: str,
) -> None:
    stale_values = {
        Timeframe.M15: datetime(2026, 8, 18, 9, 30, tzinfo=UTC),
        Timeframe.H1: datetime(2026, 8, 18, 8, 0, tzinfo=UTC),
        Timeframe.H4: datetime(2026, 8, 18, 0, 0, tzinfo=UTC),
        Timeframe.DAILY: datetime(2026, 8, 16, 0, 0, tzinfo=UTC),
        Timeframe.WEEKLY: datetime(2026, 8, 3, 0, 0, tzinfo=UTC),
    }
    history = _copy_history()
    for timeframe in stale_timeframes:
        history = _replace_latest(history, timeframe, stale_values[timeframe])

    assert _evaluate(_context(history=history)).reason_code == expected_code


def test_research_replay_is_explicitly_rejected_without_live_quote_rules() -> None:
    assessment = _evaluate(
        _context(
            mode=AurumDataMode.RESEARCH_REPLAY,
            quote_available=False,
            quote_timestamp=None,
        )
    )

    assert assessment.reason_code == "LIVE_FRESHNESS_CONTEXT_INVALID"
    assert assessment.reason is not None
    assert "REAL_READ_ONLY" in assessment.reason


# Gap-aware HTF evidence amendment.


def _friday_to_monday_history() -> dict[Timeframe, tuple[datetime, ...]]:
    return {
        Timeframe.M5: (
            datetime(2026, 8, 14, 20, 0, tzinfo=UTC),
            datetime(2026, 8, 14, 23, 0, tzinfo=UTC),
            datetime(2026, 8, 14, 23, 45, tzinfo=UTC),
            datetime(2026, 8, 14, 23, 55, tzinfo=UTC),
            datetime(2026, 8, 17, 0, 0, tzinfo=UTC),
        ),
        Timeframe.M15: (datetime(2026, 8, 14, 23, 45, tzinfo=UTC),),
        Timeframe.H1: (datetime(2026, 8, 14, 23, 0, tzinfo=UTC),),
        Timeframe.H4: (
            datetime(2026, 8, 3, 0, 0, tzinfo=UTC),
            datetime(2026, 8, 10, 0, 0, tzinfo=UTC),
            datetime(2026, 8, 14, 20, 0, tzinfo=UTC),
        ),
        Timeframe.DAILY: (datetime(2026, 8, 14, 0, 0, tzinfo=UTC),),
        Timeframe.WEEKLY: (datetime(2026, 8, 10, 0, 0, tzinfo=UTC),),
    }


def _friday_to_monday_context() -> FreshnessContext:
    observation = datetime(2026, 8, 17, 0, 0, tzinfo=UTC)
    boundary = observation + timedelta(minutes=5)
    return _context(
        observation_time=observation,
        decision_available_at=boundary,
        generated_at=boundary + timedelta(seconds=1),
        quote_timestamp=boundary,
        history=_friday_to_monday_history(),
    )


def test_friday_to_monday_gap_does_not_expect_sunday_m15() -> None:
    assert _evaluate(_friday_to_monday_context()).valid is True


def test_friday_to_monday_gap_does_not_expect_sunday_h1() -> None:
    assert _evaluate(_friday_to_monday_context()).valid is True


def test_friday_to_monday_gap_does_not_expect_nonexistent_h4() -> None:
    assert _evaluate(_friday_to_monday_context()).valid is True


def test_newly_completed_m15_backed_by_m5_advances_expected_m15() -> None:
    observation = datetime(2026, 8, 18, 10, 10, tzinfo=UTC)
    boundary = observation + timedelta(minutes=5)
    history = _copy_history()
    history[Timeframe.M5] = (*history[Timeframe.M5], observation)
    history = _replace_latest(
        history,
        Timeframe.M15,
        datetime(2026, 8, 18, 10, 0, tzinfo=UTC),
    )

    assessment = _evaluate(
        _context(
            observation_time=observation,
            decision_available_at=boundary,
            generated_at=boundary + timedelta(seconds=1),
            quote_timestamp=boundary,
            history=history,
        )
    )

    assert assessment.valid is True


def test_lagging_m15_with_completed_m5_evidence_is_stale() -> None:
    observation = datetime(2026, 8, 18, 10, 10, tzinfo=UTC)
    boundary = observation + timedelta(minutes=5)
    history = _copy_history()
    history[Timeframe.M5] = (*history[Timeframe.M5], observation)

    assessment = _evaluate(
        _context(
            observation_time=observation,
            decision_available_at=boundary,
            generated_at=boundary + timedelta(seconds=1),
            quote_timestamp=boundary,
            history=history,
        )
    )

    assert assessment.reason_code == "LIVE_M15_STALE"


def test_lagging_h1_with_completed_m5_evidence_is_stale() -> None:
    observation = datetime(2026, 8, 18, 10, 55, tzinfo=UTC)
    boundary = observation + timedelta(minutes=5)
    history = _copy_history()
    history[Timeframe.M5] = (*history[Timeframe.M5], observation)
    history = _replace_latest(
        history,
        Timeframe.M15,
        datetime(2026, 8, 18, 10, 45, tzinfo=UTC),
    )

    assessment = _evaluate(
        _context(
            observation_time=observation,
            decision_available_at=boundary,
            generated_at=boundary + timedelta(seconds=1),
            quote_timestamp=boundary,
            history=history,
        )
    )

    assert assessment.reason_code == "LIVE_H1_STALE"


def test_lagging_h4_with_completed_m5_evidence_is_stale() -> None:
    observation = datetime(2026, 8, 18, 11, 55, tzinfo=UTC)
    boundary = observation + timedelta(minutes=5)
    history = _copy_history()
    history[Timeframe.M5] = (*history[Timeframe.M5], observation)
    history = _replace_latest(
        history,
        Timeframe.M15,
        datetime(2026, 8, 18, 11, 45, tzinfo=UTC),
    )
    history = _replace_latest(
        history,
        Timeframe.H1,
        datetime(2026, 8, 18, 11, 0, tzinfo=UTC),
    )

    assessment = _evaluate(
        _context(
            observation_time=observation,
            decision_available_at=boundary,
            generated_at=boundary + timedelta(seconds=1),
            quote_timestamp=boundary,
            history=history,
        )
    )

    assert assessment.reason_code == "LIVE_H4_STALE"


def test_missing_calendar_bucket_without_m5_evidence_does_not_cause_stale() -> None:
    assessment = _evaluate(_friday_to_monday_context())

    assert assessment.valid is True


def test_provider_gap_does_not_require_fixed_m5_count_per_bucket() -> None:
    observation = datetime(2026, 8, 18, 10, 10, tzinfo=UTC)
    boundary = observation + timedelta(minutes=5)
    history = _copy_history()
    history[Timeframe.M5] = (
        datetime(2026, 8, 18, 4, 0, tzinfo=UTC),
        datetime(2026, 8, 18, 9, 0, tzinfo=UTC),
        observation,
    )
    history = _replace_latest(
        history,
        Timeframe.M15,
        datetime(2026, 8, 18, 10, 0, tzinfo=UTC),
    )

    assessment = _evaluate(
        _context(
            observation_time=observation,
            decision_available_at=boundary,
            generated_at=boundary + timedelta(seconds=1),
            quote_timestamp=boundary,
            history=history,
        )
    )

    assert assessment.valid is True


def test_d1_expected_value_comes_from_actual_h4_completed_buckets() -> None:
    history = _copy_history()
    history[Timeframe.H4] = (
        datetime(2026, 8, 10, 0, 0, tzinfo=UTC),
        datetime(2026, 8, 16, 20, 0, tzinfo=UTC),
        datetime(2026, 8, 18, 4, 0, tzinfo=UTC),
    )
    history[Timeframe.DAILY] = (datetime(2026, 8, 16, 0, 0, tzinfo=UTC),)

    assessment = _evaluate(_context(history=history))

    assert assessment.valid is True


def test_w1_expected_value_comes_from_actual_h4_completed_buckets() -> None:
    observation = datetime(2026, 8, 24, 0, 0, tzinfo=UTC)
    boundary = observation + timedelta(minutes=5)
    history = {
        Timeframe.M5: (
            datetime(2026, 8, 14, 20, 0, tzinfo=UTC),
            datetime(2026, 8, 14, 23, 45, tzinfo=UTC),
            datetime(2026, 8, 14, 23, 55, tzinfo=UTC),
            observation,
        ),
        Timeframe.M15: (datetime(2026, 8, 14, 23, 45, tzinfo=UTC),),
        Timeframe.H1: (datetime(2026, 8, 14, 23, 0, tzinfo=UTC),),
        Timeframe.H4: (
            datetime(2026, 8, 3, 0, 0, tzinfo=UTC),
            datetime(2026, 8, 14, 20, 0, tzinfo=UTC),
        ),
        Timeframe.DAILY: (datetime(2026, 8, 14, 0, 0, tzinfo=UTC),),
        Timeframe.WEEKLY: (datetime(2026, 8, 10, 0, 0, tzinfo=UTC),),
    }

    assessment = _evaluate(
        _context(
            observation_time=observation,
            decision_available_at=boundary,
            generated_at=boundary + timedelta(seconds=1),
            quote_timestamp=boundary,
            history=history,
        )
    )

    assert assessment.valid is True


def test_weekend_gap_does_not_manufacture_sunday_d1() -> None:
    assessment = _evaluate(_friday_to_monday_context())

    assert assessment.valid is True


def test_stale_h4_precedes_d1_and_w1_failures() -> None:
    history = _copy_history()
    history = _replace_latest(
        history,
        Timeframe.H4,
        datetime(2026, 8, 18, 0, 0, tzinfo=UTC),
    )
    history = _replace_latest(
        history,
        Timeframe.DAILY,
        datetime(2026, 8, 16, 0, 0, tzinfo=UTC),
    )
    history = _replace_latest(
        history,
        Timeframe.WEEKLY,
        datetime(2026, 8, 3, 0, 0, tzinfo=UTC),
    )

    assert _evaluate(_context(history=history)).reason_code == "LIVE_H4_STALE"


def test_valid_h4_with_inconsistent_d1_returns_live_d1_stale() -> None:
    history = _replace_latest(
        _copy_history(),
        Timeframe.DAILY,
        datetime(2026, 8, 16, 0, 0, tzinfo=UTC),
    )

    assert _evaluate(_context(history=history)).reason_code == "LIVE_D1_STALE"


def test_valid_h4_with_inconsistent_w1_returns_live_w1_stale() -> None:
    history = _replace_latest(
        _copy_history(),
        Timeframe.WEEKLY,
        datetime(2026, 8, 3, 0, 0, tzinfo=UTC),
    )

    assert _evaluate(_context(history=history)).reason_code == "LIVE_W1_STALE"


def test_target_actual_newer_than_lower_timeframe_evidence_is_invalid() -> None:
    history = _replace_latest(
        _copy_history(),
        Timeframe.M15,
        datetime(2026, 8, 18, 10, 0, tzinfo=UTC),
    )

    assert (
        _evaluate(_context(history=history)).reason_code
        == "LIVE_FRESHNESS_CONTEXT_INVALID"
    )


@pytest.mark.parametrize("timeframe", [Timeframe.M5, Timeframe.H4])
def test_insufficient_m5_or_h4_evidence_is_invalid(timeframe: Timeframe) -> None:
    history = _copy_history()
    history[timeframe] = ()

    assert (
        _evaluate(_context(history=history)).reason_code
        == "LIVE_FRESHNESS_CONTEXT_INVALID"
    )


def test_d1_and_w1_use_repository_completed_period_buckets() -> None:
    source = inspect.getsource(live_freshness)

    assert "completed_period_buckets(" in source


def test_production_policy_has_no_trading_session_calendar_assumptions() -> None:
    source = inspect.getsource(live_freshness).lower()
    prohibited = (
        "friday",
        "saturday",
        "sunday",
        "weekend",
        "market_open",
        "market_close",
        "session hours",
        "holiday",
    )

    for token in prohibited:
        assert token not in source


_CURRENTNESS_BASE = datetime(2026, 8, 18, 10, 5, tzinfo=UTC)


def _currentness_snapshot(
    *,
    quote_available: bool = True,
    quote_timestamp: datetime | None = _CURRENTNESS_BASE,
    decision_available_at: datetime = _CURRENTNESS_BASE,
) -> SimpleNamespace:
    return SimpleNamespace(
        quote=SimpleNamespace(
            available=quote_available,
            observed_at_utc=quote_timestamp,
        ),
        meta=SimpleNamespace(
            decision_available_at_utc=decision_available_at,
        ),
    )


def test_currentness_exact_quote_threshold_is_current() -> None:
    now = _CURRENTNESS_BASE + timedelta(seconds=MAX_QUOTE_AGE_SECONDS)
    snapshot = _currentness_snapshot(
        quote_timestamp=_CURRENTNESS_BASE,
        decision_available_at=now,
    )

    currentness = evaluate_live_snapshot_currentness(snapshot, now_utc=now)

    assert currentness.current is True
    assert currentness.reason_code is None


def test_currentness_quote_just_above_threshold_is_stale() -> None:
    now = _CURRENTNESS_BASE + timedelta(
        seconds=MAX_QUOTE_AGE_SECONDS,
        microseconds=1,
    )
    snapshot = _currentness_snapshot(
        quote_timestamp=_CURRENTNESS_BASE,
        decision_available_at=now,
    )

    currentness = evaluate_live_snapshot_currentness(snapshot, now_utc=now)

    assert currentness.current is False
    assert currentness.reason_code == "LIVE_QUOTE_STALE"


def test_currentness_exact_m5_threshold_is_current_when_quote_is_current() -> None:
    now = _CURRENTNESS_BASE + timedelta(seconds=MAX_M5_DECISION_DELAY_SECONDS)
    snapshot = _currentness_snapshot(
        quote_timestamp=now,
        decision_available_at=_CURRENTNESS_BASE,
    )

    currentness = evaluate_live_snapshot_currentness(snapshot, now_utc=now)

    assert currentness.current is True
    assert currentness.reason_code is None


def test_currentness_m5_just_above_threshold_is_stale() -> None:
    now = _CURRENTNESS_BASE + timedelta(
        seconds=MAX_M5_DECISION_DELAY_SECONDS,
        microseconds=1,
    )
    snapshot = _currentness_snapshot(
        quote_timestamp=now,
        decision_available_at=_CURRENTNESS_BASE,
    )

    currentness = evaluate_live_snapshot_currentness(snapshot, now_utc=now)

    assert currentness.current is False
    assert currentness.reason_code == "LIVE_M5_STALE"


def test_currentness_unavailable_quote_fails_closed() -> None:
    snapshot = _currentness_snapshot(
        quote_available=False,
        quote_timestamp=None,
    )

    currentness = evaluate_live_snapshot_currentness(
        snapshot,
        now_utc=_CURRENTNESS_BASE,
    )

    assert currentness.current is False
    assert currentness.reason_code == "LIVE_QUOTE_UNAVAILABLE"


def test_currentness_invalid_timestamp_evidence_fails_closed() -> None:
    snapshot = _currentness_snapshot(
        decision_available_at=datetime(2026, 8, 18, 10, 5),  # noqa: DTZ001
    )

    currentness = evaluate_live_snapshot_currentness(
        snapshot,
        now_utc=_CURRENTNESS_BASE,
    )

    assert currentness.current is False
    assert currentness.reason_code == "LIVE_FRESHNESS_CONTEXT_INVALID"


def test_currentness_invalid_evidence_precedes_quote_unavailable() -> None:
    snapshot = _currentness_snapshot(
        quote_available=False,
        quote_timestamp=None,
        decision_available_at=datetime(2026, 8, 18, 10, 5),  # noqa: DTZ001
    )

    currentness = evaluate_live_snapshot_currentness(
        snapshot,
        now_utc=_CURRENTNESS_BASE,
    )

    assert currentness.reason_code == "LIVE_FRESHNESS_CONTEXT_INVALID"


def test_currentness_stale_quote_precedes_stale_m5() -> None:
    now = _CURRENTNESS_BASE + timedelta(seconds=31)
    snapshot = _currentness_snapshot(
        quote_timestamp=_CURRENTNESS_BASE,
        decision_available_at=_CURRENTNESS_BASE,
    )

    currentness = evaluate_live_snapshot_currentness(snapshot, now_utc=now)

    assert currentness.reason_code == "LIVE_QUOTE_STALE"


def test_currentness_evaluator_does_not_mutate_snapshot() -> None:
    snapshot = _currentness_snapshot()
    quote_before = (
        snapshot.quote.available,
        snapshot.quote.observed_at_utc,
    )
    decision_before = snapshot.meta.decision_available_at_utc

    evaluate_live_snapshot_currentness(snapshot, now_utc=_CURRENTNESS_BASE)

    assert snapshot.quote.available == quote_before[0]
    assert snapshot.quote.observed_at_utc == quote_before[1]
    assert snapshot.meta.decision_available_at_utc == decision_before


def test_currentness_evaluator_rechecks_only_quote_and_m5_time_decay() -> None:
    source = inspect.getsource(evaluate_live_snapshot_currentness)

    assert "LIVE_M15_STALE" not in source
    assert "LIVE_H1_STALE" not in source
    assert "LIVE_H4_STALE" not in source
    assert "LIVE_D1_STALE" not in source
    assert "LIVE_W1_STALE" not in source


def test_currentness_evaluator_has_no_reads_analytics_risk_or_ready_logic() -> None:
    source = inspect.getsource(evaluate_live_snapshot_currentness)

    prohibited = (
        "MetaTrader5",
        "mt5.",
        "QuoteReader",
        ".read(",
        "MarketDataService",
        "process_multi_timeframe",
        "AurumReadModelBuilder",
        "RiskManager",
        "READY_BUY",
        "READY_SELL",
    )
    for token in prohibited:
        assert token not in source
