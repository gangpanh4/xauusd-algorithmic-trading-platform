"""Validation and reporting for execution-reconciliation audit JSONL."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final


class ExecutionReconciliationReportError(ValueError):
    """Raised when audit evidence is malformed, unsafe, or inconsistent."""


class ExecutionReconciliationReporter:
    """Validate immutable audit evidence and export deterministic summaries."""

    REQUIRED_FIELDS: Final[frozenset[str]] = frozenset(
        {
            "recorded_at",
            "intent_key",
            "broker_comment",
            "magic_number",
            "intent_status_before",
            "intent_status_after",
            "reconciliation_disposition",
            "matching_order_ticket",
            "matching_deal_tickets",
            "active_order_match_count",
            "historical_order_match_count",
            "execution_deal_match_count",
            "open_position_match_count",
            "startup_allowed",
            "automatic_resubmission_attempted",
            "live_execution_enabled",
            "shadow_only",
            "trade_executed",
            "failure_reason",
        }
    )

    def __init__(
        self,
        *,
        input_path: str | Path,
        output_directory: str | Path,
    ) -> None:
        self.input_path = Path(input_path)
        self.output_directory = Path(output_directory)

    def calculate(self) -> dict[str, Any]:
        if not self.input_path.is_file():
            raise FileNotFoundError(
                f"Reconciliation audit file does not exist: {self.input_path}"
            )

        valid_rows: list[dict[str, Any]] = []
        parse_error_count = 0
        schema_error_count = 0
        semantic_violation_count = 0
        duplicate_count = 0
        out_of_order_count = 0
        seen: set[tuple[str, datetime]] = set()
        previous: datetime | None = None
        dispositions: Counter[str] = Counter()

        with self.input_path.open(encoding="utf-8") as handle:
            for raw in handle:
                line = raw.strip()
                if not line:
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    parse_error_count += 1
                    continue
                if not isinstance(value, dict) or set(value) != self.REQUIRED_FIELDS:
                    schema_error_count += 1
                    continue
                try:
                    recorded_at = datetime.fromisoformat(value["recorded_at"])
                    if recorded_at.tzinfo is None or recorded_at.utcoffset() is None:
                        raise ValueError
                    recorded_at = recorded_at.astimezone(UTC)
                except (TypeError, ValueError):
                    schema_error_count += 1
                    continue

                identity = (str(value["intent_key"]), recorded_at)
                if identity in seen:
                    duplicate_count += 1
                seen.add(identity)
                if previous is not None and recorded_at < previous:
                    out_of_order_count += 1
                previous = recorded_at

                unsafe = (
                    bool(value["automatic_resubmission_attempted"])
                    or bool(value["trade_executed"])
                    or bool(value["live_execution_enabled"])
                    or not bool(value["shadow_only"])
                )
                contradictory = (
                    str(value["reconciliation_disposition"]) == "FAILED_CLOSED"
                    and bool(value["startup_allowed"])
                )
                if unsafe or contradictory:
                    semantic_violation_count += 1

                dispositions[str(value["reconciliation_disposition"])] += 1
                valid_rows.append(value)

        if not valid_rows:
            raise ExecutionReconciliationReportError(
                "Reconciliation audit contains no valid rows."
            )

        validation_passed = (
            parse_error_count == 0
            and schema_error_count == 0
            and semantic_violation_count == 0
            and duplicate_count == 0
            and out_of_order_count == 0
        )
        return {
            "input_path": str(self.input_path),
            "total_audit_rows": len(valid_rows),
            "parse_error_count": parse_error_count,
            "schema_error_count": schema_error_count,
            "semantic_violation_count": semantic_violation_count,
            "duplicate_record_count": duplicate_count,
            "out_of_order_count": out_of_order_count,
            "startup_allowed_count": sum(
                bool(row["startup_allowed"]) for row in valid_rows
            ),
            "startup_blocked_count": sum(
                not bool(row["startup_allowed"]) for row in valid_rows
            ),
            "disposition_counts": dict(sorted(dispositions.items())),
            "automatic_resubmission_attempted": any(
                bool(row["automatic_resubmission_attempted"])
                for row in valid_rows
            ),
            "trade_executed": any(
                bool(row["trade_executed"]) for row in valid_rows
            ),
            "live_execution_enabled": any(
                bool(row["live_execution_enabled"]) for row in valid_rows
            ),
            "shadow_only": all(
                bool(row["shadow_only"]) for row in valid_rows
            ),
            "validation_passed": validation_passed,
        }

    def export(self) -> tuple[Path, Path]:
        summary = self.calculate()
        self.output_directory.mkdir(parents=True, exist_ok=True)
        json_path = (
            self.output_directory
            / "execution_reconciliation_summary.json"
        )
        csv_path = (
            self.output_directory
            / "execution_reconciliation_summary.csv"
        )
        json_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        flat = {
            **summary,
            "disposition_counts": json.dumps(
                summary["disposition_counts"],
                sort_keys=True,
            ),
        }
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(flat))
            writer.writeheader()
            writer.writerow(flat)
        return csv_path, json_path
