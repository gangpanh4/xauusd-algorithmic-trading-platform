"""Sustained read-only monitoring for connected demo reconciliation."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import MetaTrader5 as mt5

from .config import LiveTradingConfig
from .connected_reconciliation_probe import (
    ConnectedReconciliationProbeError,
    ConnectedReconciliationProbeResult,
    run_connected_demo_read_only_probe,
)


class SustainedReconciliationMonitorError(RuntimeError):
    """Raised when sustained monitoring cannot continue safely."""


@dataclass(frozen=True, slots=True)
class SustainedReconciliationSample:
    """One immutable read-only monitoring sample."""

    sequence: int
    captured_at: datetime
    result: ConnectedReconciliationProbeResult
    state_changed: bool
    change_fields: tuple[str, ...]
    alert_required: bool
    alert_reasons: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["captured_at"] = self.captured_at.astimezone(UTC).isoformat()
        payload["result"] = self.result.to_payload()
        payload["change_fields"] = list(self.change_fields)
        payload["alert_reasons"] = list(self.alert_reasons)
        return payload


@dataclass(frozen=True, slots=True)
class SustainedReconciliationSummary:
    """Aggregate validation for an append-only monitoring session."""

    generated_at: datetime
    sample_count: int
    state_change_count: int
    alert_count: int
    disposition_counts: dict[str, int]
    demo_account_consistent: bool
    account_identity_consistent: bool
    live_execution_enabled: bool
    order_submission_attempted: bool
    trade_executed: bool
    shadow_only: bool
    validation_passed: bool

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["generated_at"] = self.generated_at.astimezone(UTC).isoformat()
        return payload


def build_monitoring_sample(
    *,
    sequence: int,
    result: ConnectedReconciliationProbeResult,
    previous: ConnectedReconciliationProbeResult | None,
    captured_at: datetime | None = None,
) -> SustainedReconciliationSample:
    """Compare one probe result with the prior read-only result."""

    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise ValueError("sequence must be a positive integer")

    changes: list[str] = []
    if previous is not None:
        comparable = (
            "account_login",
            "account_server",
            "account_trade_mode",
            "persisted_intent_present",
            "persisted_intent_key",
            "persisted_intent_status_before",
            "reconciled_intent_status",
            "reconciliation_disposition",
            "matching_order_ticket",
            "matching_deal_tickets",
            "active_order_count",
            "historical_order_count",
            "execution_deal_count",
            "open_position_count",
        )
        for field_name in comparable:
            if getattr(previous, field_name) != getattr(result, field_name):
                changes.append(field_name)

    alerts: list[str] = []
    if not result.demo_account_confirmed:
        alerts.append("DEMO_ACCOUNT_NOT_CONFIRMED")
    if result.live_execution_enabled:
        alerts.append("LIVE_EXECUTION_ENABLED")
    if not result.shadow_only:
        alerts.append("SHADOW_ONLY_FALSE")
    if result.order_submission_attempted:
        alerts.append("ORDER_SUBMISSION_ATTEMPTED")
    if result.trade_executed:
        alerts.append("TRADE_EXECUTED")
    if not result.validation_passed:
        alerts.append("PROBE_VALIDATION_FAILED")
    if result.reconciliation_disposition == "FAILED_CLOSED":
        alerts.append("RECONCILIATION_FAILED_CLOSED")
    if previous is not None and (
        previous.account_login != result.account_login
        or previous.account_server != result.account_server
        or previous.account_trade_mode != result.account_trade_mode
    ):
        alerts.append("ACCOUNT_IDENTITY_CHANGED")

    timestamp = (
        datetime.now(UTC)
        if captured_at is None
        else _aware_utc(captured_at, "captured_at")
    )
    return SustainedReconciliationSample(
        sequence=sequence,
        captured_at=timestamp,
        result=result,
        state_changed=bool(changes),
        change_fields=tuple(changes),
        alert_required=bool(alerts),
        alert_reasons=tuple(alerts),
    )


def append_monitoring_sample(
    path: str | Path,
    sample: SustainedReconciliationSample,
) -> None:
    """Append and fsync one monitoring sample as JSONL."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(
        sample.to_payload(),
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    try:
        with target.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise SustainedReconciliationMonitorError(
            f"Unable to append sustained reconciliation evidence: {target}"
        ) from exc


def summarize_monitoring_samples(
    samples: tuple[SustainedReconciliationSample, ...],
    *,
    generated_at: datetime | None = None,
) -> SustainedReconciliationSummary:
    """Validate one sustained read-only monitoring session."""

    if not samples:
        raise ValueError("samples must not be empty")

    dispositions = Counter(
        sample.result.reconciliation_disposition for sample in samples
    )
    first = samples[0].result
    account_identity_consistent = all(
        sample.result.account_login == first.account_login
        and sample.result.account_server == first.account_server
        and sample.result.account_trade_mode == first.account_trade_mode
        for sample in samples
    )
    demo_account_consistent = all(
        sample.result.demo_account_confirmed for sample in samples
    )
    live_enabled = any(
        sample.result.live_execution_enabled for sample in samples
    )
    submission_attempted = any(
        sample.result.order_submission_attempted for sample in samples
    )
    trade_executed = any(sample.result.trade_executed for sample in samples)
    shadow_only = all(sample.result.shadow_only for sample in samples)
    alerts = sum(sample.alert_required for sample in samples)

    return SustainedReconciliationSummary(
        generated_at=(
            datetime.now(UTC)
            if generated_at is None
            else _aware_utc(generated_at, "generated_at")
        ),
        sample_count=len(samples),
        state_change_count=sum(sample.state_changed for sample in samples),
        alert_count=alerts,
        disposition_counts=dict(sorted(dispositions.items())),
        demo_account_consistent=demo_account_consistent,
        account_identity_consistent=account_identity_consistent,
        live_execution_enabled=live_enabled,
        order_submission_attempted=submission_attempted,
        trade_executed=trade_executed,
        shadow_only=shadow_only,
        validation_passed=(
            demo_account_consistent
            and account_identity_consistent
            and not live_enabled
            and not submission_attempted
            and not trade_executed
            and shadow_only
            and alerts == 0
        ),
    )


def export_monitoring_summary(
    path: str | Path,
    summary: SustainedReconciliationSummary,
) -> Path:
    """Export deterministic monitoring summary JSON."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(summary.to_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def run_sustained_monitoring(
    *,
    config: LiveTradingConfig,
    iterations: int,
    interval_seconds: float,
    lookback_hours: int,
    evidence_path: str | Path,
    summary_path: str | Path,
    probe_runner: Callable[..., ConnectedReconciliationProbeResult] = (
        run_connected_demo_read_only_probe
    ),
    sleeper: Callable[[float], None] = time.sleep,
) -> SustainedReconciliationSummary:
    """Run repeated connected probes without enabling order submission."""

    if config.live_execution_enabled:
        raise SustainedReconciliationMonitorError(
            "Sustained monitoring requires live_execution_enabled=False."
        )
    if isinstance(iterations, bool) or not isinstance(iterations, int):
        raise TypeError("iterations must be an integer")
    if iterations < 1:
        raise ValueError("iterations must be at least one")
    if interval_seconds < 0:
        raise ValueError("interval_seconds must not be negative")

    samples: list[SustainedReconciliationSample] = []
    previous: ConnectedReconciliationProbeResult | None = None

    for sequence in range(1, iterations + 1):
        result = probe_runner(
            config=config,
            lookback_hours=lookback_hours,
        )
        sample = build_monitoring_sample(
            sequence=sequence,
            result=result,
            previous=previous,
        )
        append_monitoring_sample(evidence_path, sample)
        samples.append(sample)
        previous = result

        if sample.alert_required:
            raise SustainedReconciliationMonitorError(
                "Sustained reconciliation monitoring detected: "
                + ", ".join(sample.alert_reasons)
            )
        if sequence < iterations:
            sleeper(interval_seconds)

    summary = summarize_monitoring_samples(tuple(samples))
    export_monitoring_summary(summary_path, summary)
    return summary


def main() -> int:
    """Run sustained connected demo monitoring from the command line."""

    parser = argparse.ArgumentParser(
        description=(
            "Repeatedly query a connected MT5 demo account read-only and "
            "record append-only reconciliation evidence."
        )
    )
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--iterations", type=int, default=12)
    parser.add_argument("--interval-seconds", type=float, default=300.0)
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument(
        "--evidence",
        default=(
            "runtime/connected_demo_reconciliation_monitor.jsonl"
        ),
    )
    parser.add_argument(
        "--summary",
        default=(
            "output/live_execution_reconciliation/"
            "connected_demo_monitor_summary.json"
        ),
    )
    args = parser.parse_args()

    initialized = False
    try:
        if not mt5.initialize():
            raise SustainedReconciliationMonitorError(
                f"Unable to initialize MT5: {mt5.last_error()}"
            )
        initialized = True
        summary = run_sustained_monitoring(
            config=LiveTradingConfig(
                symbol=args.symbol,
                live_execution_enabled=False,
            ),
            iterations=args.iterations,
            interval_seconds=args.interval_seconds,
            lookback_hours=args.lookback_hours,
            evidence_path=args.evidence,
            summary_path=args.summary,
        )
        print(json.dumps(summary.to_payload(), indent=2, sort_keys=True))
        return 0 if summary.validation_passed else 1
    except (
        ConnectedReconciliationProbeError,
        SustainedReconciliationMonitorError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"Sustained read-only monitoring failed closed: {exc}")
        return 2
    finally:
        if initialized:
            mt5.shutdown()


def _aware_utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


if __name__ == "__main__":
    raise SystemExit(main())
