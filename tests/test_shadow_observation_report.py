from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from core.live_trading.shadow_observation_report import (
    ShadowObservationReporter,
    ShadowObservationValidationError,
)


def _row(
    timestamp: datetime,
    *,
    session_id: str | None = None,
    session_started_at: datetime | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "timestamp": timestamp.isoformat(),
        "symbol": "XAUUSD",
        "live_execution_enabled": False,
        "shadow_only": True,
        "trade_executed": False,
        "signal_present": True,
        "trade_plan_present": True,
        "direction": "HOLD",
        "decision": "SKIP",
        "entry_price": 0.0,
        "stop_loss": 0.0,
        "take_profit": 0.0,
        "position_size": 0.0,
        "risk_reward_ratio": 0.0,
        "reason": "No trading opportunity.",
    }
    if session_id is not None:
        row["session_id"] = session_id
    if session_started_at is not None:
        row["session_started_at"] = session_started_at.isoformat()
    return row


def _write(path, rows) -> None:
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_exports_valid_append_only_shadow_summary(tmp_path) -> None:
    source = tmp_path / "shadow.jsonl"
    start = datetime(2026, 8, 5, 4, 10, tzinfo=UTC)
    _write(
        source,
        [
            _row(start),
            _row(start + timedelta(minutes=5)),
            _row(start + timedelta(minutes=15)),
        ],
    )

    reporter = ShadowObservationReporter(
        input_path=source,
        output_directory=tmp_path / "output",
    )
    csv_path, json_path = reporter.export()
    summary = json.loads(json_path.read_text(encoding="utf-8"))

    assert csv_path.exists()
    assert summary["total_observations"] == 3
    assert summary["five_minute_intervals"] == 1
    assert summary["gap_count"] == 1
    assert summary["gap_minutes"] == [10.0]
    assert summary["decision_counts"] == {"SKIP": 3}
    assert summary["direction_counts"] == {"HOLD": 3}
    assert summary["validation_passed"] is True
    assert summary["explicit_session_count"] == 0
    assert summary["legacy_observation_count"] == 3
    assert summary["active_pipeline_modified"] is False
    assert summary["source_file_modified"] is False


def test_duplicate_timestamp_fails_closed(tmp_path) -> None:
    source = tmp_path / "shadow.jsonl"
    timestamp = datetime(2026, 8, 5, 4, 10, tzinfo=UTC)
    _write(source, [_row(timestamp), _row(timestamp)])

    reporter = ShadowObservationReporter(
        input_path=source,
        output_directory=tmp_path / "output",
    )

    with pytest.raises(
        ShadowObservationValidationError,
        match="chronology",
    ):
        reporter.calculate()


def test_execution_safety_violation_fails_closed(tmp_path) -> None:
    source = tmp_path / "shadow.jsonl"
    row = _row(datetime(2026, 8, 5, 4, 10, tzinfo=UTC))
    row["trade_executed"] = True
    _write(source, [row])

    reporter = ShadowObservationReporter(
        input_path=source,
        output_directory=tmp_path / "output",
    )

    with pytest.raises(
        ShadowObservationValidationError,
        match="safety",
    ):
        reporter.calculate()


def test_skip_with_nonzero_trade_values_fails_closed(tmp_path) -> None:
    source = tmp_path / "shadow.jsonl"
    row = _row(datetime(2026, 8, 5, 4, 10, tzinfo=UTC))
    row["position_size"] = 0.01
    _write(source, [row])

    reporter = ShadowObservationReporter(
        input_path=source,
        output_directory=tmp_path / "output",
    )

    with pytest.raises(
        ShadowObservationValidationError,
        match="safety",
    ):
        reporter.calculate()


def test_explicit_sessions_are_grouped_and_counted(tmp_path) -> None:
    source = tmp_path / "shadow.jsonl"
    start = datetime(2026, 8, 5, 4, 10, tzinfo=UTC)
    second_start = start + timedelta(minutes=20)
    _write(
        source,
        [
            _row(
                start,
                session_id="session-a",
                session_started_at=start - timedelta(minutes=1),
            ),
            _row(
                start + timedelta(minutes=5),
                session_id="session-a",
                session_started_at=start - timedelta(minutes=1),
            ),
            _row(
                second_start,
                session_id="session-b",
                session_started_at=second_start - timedelta(minutes=1),
            ),
        ],
    )

    summary = ShadowObservationReporter(
        input_path=source,
        output_directory=tmp_path / "output",
    ).calculate()

    assert summary["explicit_session_count"] == 2
    assert summary["legacy_observation_count"] == 0
    assert summary["session_transition_count"] == 1
    assert [item["observation_count"] for item in summary["sessions"]] == [
        2,
        1,
    ]


def test_partial_session_metadata_fails_closed(tmp_path) -> None:
    source = tmp_path / "shadow.jsonl"
    row = _row(datetime(2026, 8, 5, 4, 10, tzinfo=UTC))
    row["session_id"] = "session-a"
    _write(source, [row])

    reporter = ShadowObservationReporter(
        input_path=source,
        output_directory=tmp_path / "output",
    )

    with pytest.raises(
        ShadowObservationValidationError,
        match="safety",
    ):
        reporter.calculate()


def test_session_start_after_observation_fails_closed(tmp_path) -> None:
    source = tmp_path / "shadow.jsonl"
    timestamp = datetime(2026, 8, 5, 4, 10, tzinfo=UTC)
    _write(
        source,
        [
            _row(
                timestamp,
                session_id="session-a",
                session_started_at=timestamp + timedelta(minutes=1),
            )
        ],
    )

    reporter = ShadowObservationReporter(
        input_path=source,
        output_directory=tmp_path / "output",
    )

    with pytest.raises(
        ShadowObservationValidationError,
        match="safety",
    ):
        reporter.calculate()
