from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from core.live_trading.shadow_observation_report import (
    ShadowObservationReporter,
    ShadowObservationValidationError,
)


def _row(timestamp: datetime) -> dict[str, object]:
    return {
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
