"""Validation and summary reporting for live shadow observations."""

from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any, Final


class ShadowObservationValidationError(ValueError):
    """Raised when shadow evidence is malformed or unsafe."""


class ShadowObservationReporter:
    """Validate append-only shadow JSONL and export deterministic summaries."""

    EXPECTED_INTERVAL_MINUTES: Final[float] = 5.0
    REQUIRED_FIELDS: Final[frozenset[str]] = frozenset(
        {
            "timestamp",
            "symbol",
            "live_execution_enabled",
            "shadow_only",
            "trade_executed",
            "signal_present",
            "trade_plan_present",
            "direction",
            "decision",
            "entry_price",
            "stop_loss",
            "take_profit",
            "position_size",
            "risk_reward_ratio",
            "reason",
        }
    )
    PIPELINE_AUDIT_FIELDS: Final[frozenset[str]] = frozenset(
        {
            "pipeline_disposition",
            "pipeline_stage_reached",
            "pipeline_rejection_stage",
            "pipeline_reason_code",
            "pipeline_reason",
            "regime_confirmed",
            "bos_present",
            "choch_present",
            "liquidity_present",
            "feature_count",
            "probability_calculated",
            "probability_accepted",
            "probability_value",
            "trade_quality_calculated",
            "trade_quality_approved",
            "trade_quality_score",
            "confluence_available",
            "confluence_approved",
            "confluence_score",
            "signal_generated",
            "risk_approved",
        }
    )
    _CSV_COLUMNS: Final[tuple[str, ...]] = (
        "Total Observations",
        "First Timestamp UTC",
        "Last Timestamp UTC",
        "Elapsed Minutes",
        "Expected Interval Minutes",
        "Five Minute Intervals",
        "Gap Count",
        "Maximum Gap Minutes",
        "Duplicate Timestamp Count",
        "Out Of Order Count",
        "Parse Error Count",
        "Schema Error Count",
        "Safety Violation Count",
        "Explicit Session Count",
        "Legacy Observation Count",
        "Session Transition Count",
        "Approved Count",
        "Rejected Count",
        "Skipped Count",
        "Hold Count",
        "Buy Count",
        "Sell Count",
        "Validation Passed",
    )

    def __init__(
        self,
        *,
        input_path: str | Path,
        output_directory: str | Path,
    ) -> None:
        self.input_path = Path(input_path)
        self.output_directory = Path(output_directory)

    def export(self) -> tuple[Path, Path]:
        """Validate the immutable input and export JSON plus one-row CSV."""

        summary = self.calculate()
        self.output_directory.mkdir(parents=True, exist_ok=True)

        json_path = (
            self.output_directory / "shadow_observation_summary.json"
        )
        json_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        csv_path = (
            self.output_directory / "shadow_observation_summary.csv"
        )
        with csv_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=list(self._CSV_COLUMNS),
                extrasaction="raise",
            )
            writer.writeheader()
            writer.writerow(self._csv_row(summary))

        return csv_path, json_path

    def calculate(self) -> dict[str, Any]:
        """Return a strict validation and summary payload."""

        if not self.input_path.exists():
            raise FileNotFoundError(
                f"Shadow observation file does not exist: {self.input_path}"
            )
        if not self.input_path.is_file():
            raise ShadowObservationValidationError(
                "Shadow observation input must be a regular file."
            )

        rows: list[Mapping[str, Any]] = []
        parse_errors: list[dict[str, Any]] = []
        schema_errors: list[dict[str, Any]] = []

        with self.input_path.open(encoding="utf-8") as file:
            for line_number, raw_line in enumerate(file, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    parse_errors.append(
                        {
                            "line": line_number,
                            "error": str(exc),
                        }
                    )
                    continue
                if not isinstance(value, Mapping):
                    schema_errors.append(
                        {
                            "line": line_number,
                            "error": "JSON value must be an object.",
                        }
                    )
                    continue

                missing = sorted(self.REQUIRED_FIELDS - set(value))
                if missing:
                    schema_errors.append(
                        {
                            "line": line_number,
                            "error": "Missing required fields.",
                            "missing_fields": missing,
                        }
                    )
                    continue
                rows.append(value)

        if parse_errors or schema_errors:
            raise ShadowObservationValidationError(
                "Shadow observation file contains parse or schema errors."
            )
        if not rows:
            raise ShadowObservationValidationError(
                "Shadow observation file contains no observations."
            )

        timestamps: list[datetime] = []
        duplicate_count = 0
        out_of_order_count = 0
        seen: set[datetime] = set()
        previous: datetime | None = None
        safety_violations: list[dict[str, Any]] = []
        semantic_violations: list[dict[str, Any]] = []

        decisions: Counter[str] = Counter()
        directions: Counter[str] = Counter()
        session_rows: dict[str, list[datetime]] = {}
        session_started_at: dict[str, datetime] = {}
        legacy_observation_count = 0
        session_transition_count = 0
        previous_session_id: str | None = None
        pipeline_audit_count = 0
        legacy_pipeline_audit_count = 0

        for index, row in enumerate(rows, start=1):
            timestamp = self._parse_timestamp(row["timestamp"], index)
            if timestamp in seen:
                duplicate_count += 1
            seen.add(timestamp)
            if previous is not None and timestamp <= previous:
                out_of_order_count += 1
            previous = timestamp
            timestamps.append(timestamp)

            decision = str(row["decision"])
            direction = str(row["direction"])
            decisions[decision] += 1
            directions[direction] += 1

            present_audit_fields = self.PIPELINE_AUDIT_FIELDS.intersection(row)
            if not present_audit_fields:
                legacy_pipeline_audit_count += 1
            elif present_audit_fields != self.PIPELINE_AUDIT_FIELDS:
                semantic_violations.append(
                    {
                        "line": index,
                        "timestamp": timestamp.isoformat(),
                        "error": "Pipeline audit fields must be complete.",
                    }
                )
            else:
                pipeline_audit_count += 1
                self._validate_pipeline_audit(
                    row=row,
                    line_number=index,
                    timestamp=timestamp,
                    semantic_violations=semantic_violations,
                )

            raw_session_id = row.get("session_id")
            raw_session_started_at = row.get("session_started_at")
            raw_recorded_at = row.get("recorded_at")
            has_session_id = raw_session_id is not None
            has_session_start = raw_session_started_at is not None
            has_recorded_at = raw_recorded_at is not None

            if has_session_id != has_session_start:
                semantic_violations.append(
                    {
                        "line": index,
                        "timestamp": timestamp.isoformat(),
                        "error": (
                            "session_id and session_started_at must either "
                            "both be present or both be absent."
                        ),
                    }
                )
            elif not has_session_id:
                if has_recorded_at:
                    semantic_violations.append(
                        {
                            "line": index,
                            "timestamp": timestamp.isoformat(),
                            "error": (
                                "recorded_at requires explicit session metadata."
                            ),
                        }
                    )
                else:
                    legacy_observation_count += 1
            else:
                if not has_recorded_at:
                    semantic_violations.append(
                        {
                            "line": index,
                            "timestamp": timestamp.isoformat(),
                            "error": (
                                "Session-aware observations require recorded_at."
                            ),
                        }
                    )
                    continue

                recorded_at = self._parse_timestamp(raw_recorded_at, index)
                if timestamp > recorded_at:
                    semantic_violations.append(
                        {
                            "line": index,
                            "timestamp": timestamp.isoformat(),
                            "error": (
                                "Observation timestamp cannot be later than recorded_at."
                            ),
                        }
                    )

                if (
                    not isinstance(raw_session_id, str)
                    or not raw_session_id.strip()
                ):
                    semantic_violations.append(
                        {
                            "line": index,
                            "timestamp": timestamp.isoformat(),
                            "error": "session_id must be a non-empty string.",
                        }
                    )
                else:
                    session_id = raw_session_id.strip()
                    started_at = self._parse_timestamp(
                        raw_session_started_at,
                        index,
                    )
                    if started_at > recorded_at:
                        semantic_violations.append(
                            {
                                "line": index,
                                "timestamp": timestamp.isoformat(),
                                "error": (
                                    "session_started_at cannot be later than recorded_at."
                                ),
                            }
                        )
                    prior_start = session_started_at.get(session_id)
                    if prior_start is not None and prior_start != started_at:
                        semantic_violations.append(
                            {
                                "line": index,
                                "timestamp": timestamp.isoformat(),
                                "error": (
                                    "A session_id must use one stable "
                                    "session_started_at value."
                                ),
                            }
                        )
                    session_started_at.setdefault(session_id, started_at)
                    session_rows.setdefault(session_id, []).append(timestamp)
                    if (
                        previous_session_id is not None
                        and session_id != previous_session_id
                    ):
                        session_transition_count += 1
                    previous_session_id = session_id

            if (
                row["live_execution_enabled"] is not False
                or row["shadow_only"] is not True
                or row["trade_executed"] is not False
            ):
                safety_violations.append(
                    {
                        "line": index,
                        "timestamp": timestamp.isoformat(),
                    }
                )

            if decision == "SKIP":
                numeric_fields = (
                    "entry_price",
                    "stop_loss",
                    "take_profit",
                    "position_size",
                )
                if any(float(row[field]) != 0.0 for field in numeric_fields):
                    semantic_violations.append(
                        {
                            "line": index,
                            "timestamp": timestamp.isoformat(),
                            "error": (
                                "SKIP observation must have zero entry, "
                                "stop, target, and position size."
                            ),
                        }
                    )

        interval_minutes = [
            (current - prior).total_seconds() / 60.0
            for prior, current in pairwise(timestamps)
        ]
        gap_values = [
            value
            for value in interval_minutes
            if value > self.EXPECTED_INTERVAL_MINUTES
        ]
        five_minute_intervals = sum(
            value == self.EXPECTED_INTERVAL_MINUTES
            for value in interval_minutes
        )

        validation_passed = not (
            duplicate_count
            or out_of_order_count
            or safety_violations
            or semantic_violations
        )
        if not validation_passed:
            raise ShadowObservationValidationError(
                "Shadow observation safety or chronology validation failed."
            )

        first = timestamps[0]
        last = timestamps[-1]
        sessions = [
            {
                "session_id": session_id,
                "session_started_at": (
                    session_started_at[session_id].isoformat()
                ),
                "observation_count": len(values),
                "first_observation_utc": values[0].isoformat(),
                "last_observation_utc": values[-1].isoformat(),
            }
            for session_id, values in sorted(
                session_rows.items(),
                key=lambda item: item[1][0],
            )
        ]
        return {
            "input_path": str(self.input_path),
            "total_observations": len(rows),
            "first_timestamp_utc": first.isoformat(),
            "last_timestamp_utc": last.isoformat(),
            "elapsed_minutes": (
                (last - first).total_seconds() / 60.0
            ),
            "expected_interval_minutes": self.EXPECTED_INTERVAL_MINUTES,
            "five_minute_intervals": five_minute_intervals,
            "gap_count": len(gap_values),
            "gap_minutes": gap_values,
            "maximum_gap_minutes": max(gap_values, default=0.0),
            "duplicate_timestamp_count": duplicate_count,
            "out_of_order_count": out_of_order_count,
            "parse_error_count": 0,
            "schema_error_count": 0,
            "safety_violation_count": len(safety_violations),
            "semantic_violation_count": len(semantic_violations),
            "explicit_session_count": len(sessions),
            "legacy_observation_count": legacy_observation_count,
            "session_transition_count": session_transition_count,
            "pipeline_audit_count": pipeline_audit_count,
            "legacy_pipeline_audit_count": legacy_pipeline_audit_count,
            "sessions": sessions,
            "decision_counts": dict(sorted(decisions.items())),
            "direction_counts": dict(sorted(directions.items())),
            "observational_only": True,
            "trade_authority": False,
            "signal_authority": False,
            "approval_authority": False,
            "position_sizing_authority": False,
            "active_pipeline_modified": False,
            "source_file_modified": False,
            "validation_passed": True,
        }

    @classmethod
    def _validate_pipeline_audit(
        cls,
        *,
        row: Mapping[str, Any],
        line_number: int,
        timestamp: datetime,
        semantic_violations: list[dict[str, Any]],
    ) -> None:
        """Validate one complete scalar pipeline-audit projection."""

        dispositions = {"ACCEPTED", "REJECTED", "SKIPPED", "ERROR"}
        stages = {
            "OBSERVATION", "REGIME", "MARKET_STRUCTURE", "FEATURES",
            "PROBABILITY", "TRADE_QUALITY", "CONFLUENCE", "SIGNAL",
            "RISK", "APPROVED",
        }
        errors: list[str] = []
        disposition = row["pipeline_disposition"]
        stage_reached = row["pipeline_stage_reached"]
        rejection_stage = row["pipeline_rejection_stage"]
        reason_code = row["pipeline_reason_code"]
        reason = row["pipeline_reason"]

        if disposition not in dispositions:
            errors.append("pipeline_disposition is invalid")
        if stage_reached not in stages:
            errors.append("pipeline_stage_reached is invalid")
        if rejection_stage is not None and rejection_stage not in stages:
            errors.append("pipeline_rejection_stage is invalid")
        if reason_code is not None and (
            not isinstance(reason_code, str) or not reason_code.strip()
        ):
            errors.append("pipeline_reason_code must be non-empty or null")
        if reason is not None and (
            not isinstance(reason, str) or not reason.strip()
        ):
            errors.append("pipeline_reason must be non-empty or null")

        boolean_fields = (
            "regime_confirmed", "bos_present", "choch_present",
            "liquidity_present", "probability_calculated",
            "probability_accepted", "trade_quality_calculated",
            "trade_quality_approved", "confluence_available",
            "confluence_approved", "signal_generated", "risk_approved",
        )
        if any(not isinstance(row[field], bool) for field in boolean_fields):
            errors.append("pipeline audit flags must be booleans")

        feature_count = row["feature_count"]
        if (
            isinstance(feature_count, bool)
            or not isinstance(feature_count, int)
            or feature_count < 0
        ):
            errors.append("feature_count must be a non-negative integer")

        for field in (
            "probability_value",
            "trade_quality_score",
            "confluence_score",
        ):
            value = row[field]
            if value is None:
                continue
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not 0.0 <= float(value) <= 1.0
            ):
                errors.append(f"{field} must be between 0 and 1 or null")

        if disposition == "ACCEPTED":
            if stage_reached != "APPROVED" or not row["risk_approved"]:
                errors.append(
                    "accepted audit must reach approval with risk approved"
                )
            if (
                rejection_stage is not None
                or reason_code is not None
                or reason is not None
            ):
                errors.append(
                    "accepted audit cannot contain rejection metadata"
                )
        elif disposition == "REJECTED":
            if rejection_stage is None or reason_code is None:
                errors.append("rejected audit requires rejection metadata")
        elif rejection_stage is not None:
            errors.append("only rejected audit may define rejection stage")

        if errors:
            semantic_violations.append(
                {
                    "line": line_number,
                    "timestamp": timestamp.isoformat(),
                    "error": "; ".join(errors),
                }
            )

    @staticmethod
    def _parse_timestamp(value: Any, line_number: int) -> datetime:
        if not isinstance(value, str):
            raise ShadowObservationValidationError(
                f"Timestamp on line {line_number} must be a string."
            )
        try:
            timestamp = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ShadowObservationValidationError(
                f"Invalid timestamp on line {line_number}."
            ) from exc
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ShadowObservationValidationError(
                f"Timestamp on line {line_number} must be timezone-aware."
            )
        return timestamp.astimezone(UTC)

    @classmethod
    def _csv_row(
        cls,
        summary: Mapping[str, Any],
    ) -> dict[str, Any]:
        decisions = summary["decision_counts"]
        directions = summary["direction_counts"]
        return {
            "Total Observations": summary["total_observations"],
            "First Timestamp UTC": summary["first_timestamp_utc"],
            "Last Timestamp UTC": summary["last_timestamp_utc"],
            "Elapsed Minutes": summary["elapsed_minutes"],
            "Expected Interval Minutes": (
                summary["expected_interval_minutes"]
            ),
            "Five Minute Intervals": summary["five_minute_intervals"],
            "Gap Count": summary["gap_count"],
            "Maximum Gap Minutes": summary["maximum_gap_minutes"],
            "Duplicate Timestamp Count": (
                summary["duplicate_timestamp_count"]
            ),
            "Out Of Order Count": summary["out_of_order_count"],
            "Parse Error Count": summary["parse_error_count"],
            "Schema Error Count": summary["schema_error_count"],
            "Safety Violation Count": (
                summary["safety_violation_count"]
            ),
            "Explicit Session Count": summary["explicit_session_count"],
            "Legacy Observation Count": (
                summary["legacy_observation_count"]
            ),
            "Session Transition Count": (
                summary["session_transition_count"]
            ),
            "Approved Count": decisions.get("APPROVE", 0),
            "Rejected Count": decisions.get("REJECT", 0),
            "Skipped Count": decisions.get("SKIP", 0),
            "Hold Count": directions.get("HOLD", 0),
            "Buy Count": directions.get("BUY", 0),
            "Sell Count": directions.get("SELL", 0),
            "Validation Passed": summary["validation_passed"],
        }
